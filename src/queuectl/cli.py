# src/queuectl/cli.py
import click

@click.group()
def cli():
    """queuectl — CLI for the job queue (work in progress)."""
    pass

@cli.command()
@click.argument('job_json')
def enqueue(job_json):
    """Enqueue a job given a JSON string (stub)."""
    click.echo(f"Enqueue called with: {job_json}")
    # TODO: validate JSON, insert into DB

@cli.group()
def worker():
    """Worker management commands."""
    pass

@worker.command('start')
@click.option('--count', default=1, show_default=True, help='Number of workers to start')
def worker_start(count):
    click.echo(f"Starting {count} worker(s) [stub]")

@worker.command('stop')
def worker_stop():
    click.echo("Stopping workers [stub]")

@cli.command()
def status():
    """Show summary status (stub)."""
    click.echo("Status [stub]")

@cli.command('list')
@click.option('--state', default=None, help='Filter by job state')
def list_jobs(state):
    click.echo(f"List jobs state={state} [stub]")

@cli.group()
def dlq():
    """Dead Letter Queue commands."""
    pass

@dlq.command('list')
def dlq_list():
    click.echo("DLQ list [stub]")

@dlq.command('retry')
@click.argument('job_id')
def dlq_retry(job_id):
    click.echo(f"Retry DLQ job {job_id} [stub]")

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
