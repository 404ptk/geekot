import discord
from discord import app_commands
import logging
import aiohttp

async def setup_steam_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int):
    guild_obj = discord.Object(id=guild_id)

    @tree.command(name="skrzynki", description="Wyświetla 15 najpopularniejszych skrzynek na rynku Steam", guild=guild_obj)
    async def skrzynki(interaction: discord.Interaction):
        await interaction.response.defer()
        
        url = "https://steamcommunity.com/market/search/render/"
        params = {
            "query": "Case",
            "start": 0,
            "count": 50,
            "search_descriptions": 0,
            "sort_column": "quantity",
            "sort_dir": "desc",
            "appid": 730,
            "category_730_Type[]": "tag_CSGO_Type_WeaponCase",
            "norender": 1,
            "currency": 6 # PLN
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            async with aiohttp.ClientSession() as session:
                all_results = []
                for start_offset in [0, 10, 20]:
                    params["start"] = start_offset
                    async with session.get(url, params=params, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and data.get("success"):
                                all_results.extend(data.get("results", []))
                            else:
                                break
                        else:
                            break
                            
                if all_results:
                    # Filtrowanie i wybranie tylko skrzynek (odrzucenie kapsuł, paczek)
                    cases = []
                    for item in all_results:
                        name_lower = item.get("name", "").lower()
                        if "case" in name_lower and "capsule" not in name_lower and "package" not in name_lower:
                            # Zapobieganie powielaniu się tej samej skrzynki między stronami
                            if not any(c.get("name") == item.get("name") for c in cases):
                                cases.append(item)
                        if len(cases) == 15:
                            break
                    
                    if not cases:
                        await interaction.followup.send("Nie znaleziono skrzynek.")
                        return

                    embed = discord.Embed(title="📦 Najpopularniejsze Skrzynki na Rynku Steam", color=discord.Color.dark_theme())
                        
                    desc = ""
                    for idx, item in enumerate(cases, 1):
                        name = item.get("name", "Nieznana skrzynka")
                        price = item.get("sell_price_text", "?")
                        quantity = item.get("sell_listings", 0)
                        if isinstance(quantity, int):
                            quantity_str = f"{quantity:,}".replace(",", " ")
                        else:
                            quantity_str = str(quantity)
                        
                        desc += f"**{idx}.** {name}\n💰 Cena: **{price}** | 📦 Dostępne: **{quantity_str}**\n\n"
                    
                    embed.description = desc
                    embed.set_footer(text="Dane pobrane z Rynku Społeczności Steam")
                    
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("Nie udało się pobrać wystarczających danych z rynku Steam.")
        except Exception as e:
            logging.error(f"Error fetching steam market cases: {e}")
            await interaction.followup.send("Wystąpił błąd podczas pobierania danych. Spróbuj ponownie później.")
