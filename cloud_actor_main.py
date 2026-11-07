"""Private cloud worker entrypoint; identical agent policy to the VPS workflow."""
import asyncio
import base64
import json
import os
from pathlib import Path
from apify import Actor


async def main():
    async with Actor:
        root = Path(__file__).resolve().parent
        os.environ['SUPERCRAFTOS_CLOUD_ACTOR'] = '1'
        private = root / 'data'
        private.mkdir(exist_ok=True, mode=0o700)
        key = base64.b64decode(os.environ['SUPERCRAFTOS_VAULT_KEY_B64'])
        (private / 'vault.key').write_bytes(key)
        (private / 'vault.key').chmod(0o600)
        import autonomous_registration as registration
        from token_optimizer import TokenOptimizer
        optimizer = TokenOptimizer()
        original_save = registration.private_json
        pending = set()
        def snapshot():
            directory = private / 'autonomous'
            credentials = {p.name: json.loads(p.read_text()) for p in directory.glob('*.credential.enc.json')}
            checkpoints = {p.name: json.loads(p.read_text()) for p in directory.glob('*.checkpoint.json')}
            accounts = {p.name: json.loads(p.read_text()) for p in directory.glob('*.account.enc.json')}
            return {'encrypted_credentials': credentials, 'encrypted_accounts': accounts, 'checkpoints': checkpoints, 'usage': optimizer.usage}
        def save(path, value):
            original_save(path, value)
            if str(path).endswith('.checkpoint.json'):
                task = asyncio.create_task(Actor.set_value('PROGRESS', snapshot()))
                pending.add(task)
                task.add_done_callback(pending.discard)
        registration.private_json = save
        run_input = await Actor.get_input() or {}
        if run_input.get('goal') == 'Verify pending Firecrawl signup through Gmail':
            report = {'gmail_verification': await registration.GmailVerificationAgent(optimizer).run()}
        else:
            report = await registration.AutonomousRegistrar(optimizer).run()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        output = snapshot()
        output['report'] = report
        await Actor.set_value('OUTPUT', output)
        Actor.log.info('Autonomous registration finished; no plaintext credentials in results')


if __name__ == '__main__':
    asyncio.run(main())
