startup_records = []


def record_startup_step(name, success, detail=None):
    detail = detail or ""
    startup_records.append((name, success, detail))

    status = "OK" if success else "FAILED"
    message = f"[Startup] {name}: {status}"
    if detail:
        message += f" - {detail}"
    print(message)


def print_startup_summary():
    total = len(startup_records)
    successful = sum(1 for _, success, _ in startup_records if success)
    failed = total - successful
    success_rate = (successful / total * 100) if total else 100.0

    print(
        f"[Startup] Summary: {successful}/{total} succeeded "
        f"({success_rate:.1f}% success, {failed} failed)."
    )

    if failed:
        failed_steps = ", ".join(name for name, success, _ in startup_records if not success)
        print(f"[Startup] Failed steps: {failed_steps}")