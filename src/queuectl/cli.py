# src/queuectl/cli.py
import click

@click.group()
def cli():
    """queuectl — CLI for the job queue (work in progress)."""
    pass

@cli.command()
@click.argument("job_json", required=False)
@click.option("--file", "job_file", type=click.Path(exists=True), help="Path to a JSON file describing the job.")
def enqueue(job_json, job_file):
    """Enqueue a job given a JSON string or --file path."""
    from .manager import enqueue_job

    # Determine input source
    if job_file:
        try:
            # Use utf-8-sig to silently handle files that include a BOM (common on Windows)
            with open(job_file, "r", encoding="utf-8-sig") as f:
                job_payload = f.read()
        except Exception as e:
            click.echo(f"Error reading job file {job_file}: {e}", err=True)
            raise SystemExit(1)
    elif job_json:
        job_payload = job_json
    else:
        click.echo("Error: You must provide either a JSON string or --file path.", err=True)
        raise SystemExit(1)

    try:
        job = enqueue_job(job_payload)
        click.echo(f"Job enqueued: id={job['id']}, state={job['state']}, max_retries={job['max_retries']}")
    except Exception as e:
        click.echo(f"Error enqueuing job: {e}", err=True)
        raise SystemExit(1)



@cli.group()
def worker():
    """Worker management commands."""
    pass

@worker.command('start')
@click.option('--count', default=1, show_default=True, help='Number of workers to start')
def worker_start(count):
    """Start one or more workers (runs in foreground). Use Ctrl+C to stop or run `worker stop` from another shell."""
    # Import here to avoid heavy imports at CLI startup
    from .worker import start_worker_processes
    try:
        print(f"Starting {count} worker(s)... (Press Ctrl+C to stop)")
        start_worker_processes(count)
    except Exception as e:
        click.echo(f"Error starting workers: {e}", err=True)
        raise SystemExit(1)

@worker.command('stop')
def worker_stop():
    """Request running workers to stop gracefully (workers check a DB flag)."""
    from .db import set_config
    try:
        set_config("workers:stop", "1")
        click.echo("Signaled workers to stop (set config workers:stop = 1).")
    except Exception as e:
        click.echo(f"Error signaling stop: {e}", err=True)
        raise SystemExit(1)


@cli.command()
def status():
    """Show summary status."""
    from .manager import status_summary
    summary = status_summary()
    counts = summary["counts"]
    click.echo("Job counts:")
    for k in ("pending", "processing", "completed", "failed", "dead"):
        click.echo(f"  {k:10s}: {counts.get(k,0)}")
    click.echo(f"workers:stop flag = {summary.get('workers_stop_flag')}")


@cli.command('list')
@click.option('--state', default=None, help='Filter by job state')
@click.option('--limit', default=100, show_default=True, help='Max number of jobs to list')
def list_jobs(state, limit):
    """List jobs optionally filtered by state."""
    from .manager import list_jobs as _list_jobs
    rows = _list_jobs(state=state, limit=limit)
    if not rows:
        click.echo("No jobs found.")
        return
    for r in rows:
        click.echo(f"{r['id']}  state={r['state']} attempts={r['attempts']} max_retries={r['max_retries']} command={r['command']}")


@cli.group()
def dlq():
    """Dead Letter Queue commands."""
    pass

@dlq.command('list')
@click.option('--limit', default=100, show_default=True, help='Max DLQ jobs to show')
def dlq_list(limit):
    from .manager import dlq_list as _dlq_list
    rows = _dlq_list(limit=limit)
    if not rows:
        click.echo("DLQ empty.")
        return
    click.echo("DLQ jobs:")
    for r in rows:
        click.echo(f"{r['id']}  attempts={r['attempts']} last_error={r['last_error']}")

@dlq.command('retry')
@click.argument('job_id')
def dlq_retry(job_id):
    """Retry a job from DLQ by job id (moves job back to pending with attempts reset)."""
    from .manager import dlq_retry as _dlq_retry
    try:
        updated = _dlq_retry(job_id)
        click.echo(f"Retried job {job_id}: state={updated['state']}, attempts={updated['attempts']}")
    except Exception as e:
        click.echo(f"Error retrying job: {e}", err=True)
        raise SystemExit(1)


@cli.group()
def config():
    """Configuration commands."""
    pass

@config.command('set')
@click.argument('key')
@click.argument('value')
def config_set(key, value):
    click.echo(f"Set config {key} = {value} [stub]")

@config.command('get')
@click.argument('key')
def config_get(key):
    click.echo(f"Get config {key} [stub]")

if __name__ == '__main__':
    cli()
