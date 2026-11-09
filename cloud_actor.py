"""Deploy and run the autonomous registrar in a private Apify cloud Actor."""
from __future__ import annotations
import asyncio
import base64
import json
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from runtime_env import ROOT, load_environment
from notion_db_setup import private_json

SOURCE_FILES = ['autonomous_registration.py', 'cloud_browser.py', 'runtime_env.py', 'token_optimizer.py', 'notion_db_setup.py', 'agent.config.yaml']
ENTRYPOINT = (ROOT / 'cloud_actor_main.py').read_text()

DOCKERFILE = '''FROM apify/actor-python-playwright:3.12
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && python -m playwright install chromium
COPY . ./
CMD ["python", "cloud_actor_main.py"]
'''
REMOTE_REQUIREMENTS = '\n'.join(['apify>=3,<5','playwright>=1.50,<2','httpx>=0.28,<1','python-dotenv>=1,<2','PyYAML>=6,<7','tiktoken>=0.8,<1','cryptography>=43','notion-client>=2.2,<3','hyperbrowser','steel-sdk']) + '\n'


def mapping(value):
    return value.model_dump(mode='json', by_alias=True) if hasattr(value, 'model_dump') else value


class ApifyRegistrationCloud:
    def __init__(self):
        load_environment()
        from apify_client import ApifyClientAsync
        self.client = ApifyClientAsync(os.environ['APIFY_API_TOKEN'])
        self.state_path = ROOT / 'data' / 'autonomous' / 'apify_runtime.json'
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}

    def record(self, **updates):
        self.state.update(updates)
        private_json(self.state_path, self.state)
        print(json.dumps({'cloud_workflow': {k:v for k,v in updates.items() if k in {'status','build_status','run_status','elapsed_seconds'}}}), flush=True)

    def sources(self):
        files = [{'name': name, 'format': 'TEXT', 'content': (ROOT / name).read_text()} for name in SOURCE_FILES]
        files.extend([{'name':'cloud_actor_main.py','format':'TEXT','content':ENTRYPOINT}, {'name':'Dockerfile','format':'TEXT','content':DOCKERFILE}, {'name':'requirements.txt','format':'TEXT','content':REMOTE_REQUIREMENTS}])
        provider = ROOT / 'data' / 'llm_provider.json'
        if provider.exists():
            files.append({'name':'data/llm_provider.json','format':'TEXT','content':provider.read_text()})
        for file in (ROOT / 'data' / 'autonomous').glob('*.account.enc.json'):
            files.append({'name':'data/autonomous/'+file.name,'format':'TEXT','content':file.read_text()})
        from autonomous_registration import pending_registration
        for file in (ROOT / 'data' / 'autonomous').glob('*.checkpoint.json'):
            if pending_registration(json.loads(file.read_text())):
                files.append({'name':'data/autonomous/'+file.name,'format':'TEXT','content':file.read_text()})
        return files

    def environment(self):
        # Secrets are runtime environment variables, excluded from source and build.
        allowed = ['GMAIL_ADDRESS','GMAIL_LOGIN_PASSWORD','GMAIL_APP_PASSWORD','X_USERNAME','X_PASSWORD','NVIDIA_API_KEY','OPENCODE_GO_API_KEY','NOTION_API_KEY','NOTION_VAULT_DB_ID','COMPOSIO_API_KEY','FIRECRAWL_API_KEY','PEERPUSH_API_KEY','DEVHUNT_API_KEY','HYPERBROWSER_API_KEY','STEEL_API_KEY']
        env = [{'name':n,'value':os.environ[n],'isSecret':True} for n in allowed if os.getenv(n)]
        key = ROOT / 'data' / 'vault.key'
        if not key.exists():
            key.write_bytes(os.urandom(32));key.chmod(0o600)
        env.append({'name':'SUPERCRAFTOS_VAULT_KEY_B64','value':base64.b64encode(key.read_bytes()).decode(),'isSecret':True})
        return env

    async def prepare(self):
        version = {'versionNumber':'0.0','sourceType':'SOURCE_FILES','sourceFiles':self.sources(),'envVars':self.environment(),'applyEnvVarsToBuild':False,'buildTag':'latest'}
        actor_id = self.state.get('actor_id')
        if not actor_id:
            existing = await self.client.actors().list(limit=100)
            for actor in existing.items:
                if mapping(actor)['name'] == 'supercraftos-registration-agent':
                    actor_id = mapping(actor)['id'];break
        if not actor_id:
            actor = await self.client.actors().create(name='supercraftos-registration-agent', title='SuperCraftOS Autonomous Registration', description='Private cloud registration workflow with bounded decisions and encrypted results.', is_public=False, versions=[version], default_run_memory_mbytes=1024, default_run_timeout=timedelta(minutes=10), restart_on_error=False)
            actor_id = mapping(actor)['id'];self.record(actor_id=actor_id,status='actor_created')
        else:
            await self.client.actor(actor_id).version('0.0').update(source_type='SOURCE_FILES',source_files=version['sourceFiles'],env_vars=version['envVars'],apply_env_vars_to_build=False,build_tag='latest')
            self.record(actor_id=actor_id,status='actor_updated')
        build = await self.client.actor(actor_id).build(version_number='0.0',tag='latest',wait_for_finish=1)
        build = mapping(build)
        self.record(build_id=build['id'],status='building')
        for _ in range(20):
            status = await self.client.build(build['id']).get()
            status = mapping(status)
            self.record(build_status=status['status'])
            if status['status'] == 'SUCCEEDED':
                return actor_id
            if status['status'] in {'FAILED','ABORTED','TIMED-OUT'}:
                raise RuntimeError('Private cloud Actor build failed')
            await asyncio.sleep(10)
        raise TimeoutError('Cloud Actor build deadline exceeded')

    async def import_output(self, run):
        record = await self.client.key_value_store(run['defaultKeyValueStoreId']).get_record('OUTPUT')
        record = mapping(record)
        if not record:
            record = mapping(await self.client.key_value_store(run['defaultKeyValueStoreId']).get_record('PROGRESS'))
            if not record:
                return {'runtime':{'status':'no_output','run_status':run['status']}}
        output = record['value']
        if isinstance(output, str):
            output = json.loads(output)
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from autonomous_registration import persist_key, PROVIDERS
        key = (ROOT / 'data' / 'vault.key').read_bytes()
        for filename, item in output.get('encrypted_credentials',{}).items():
            provider = item['provider']
            if provider not in PROVIDERS:
                continue
            encrypted = json.loads(item['encrypted'])
            secret = AESGCM(key).decrypt(base64.b64decode(encrypted['nonce']),base64.b64decode(encrypted['ciphertext']),provider.encode()).decode()
            await persist_key(provider,PROVIDERS[provider]['env'],secret)
        for filename, account in output.get('encrypted_accounts', {}).items():
            if Path(filename).name == filename and filename.endswith('.account.enc.json'):
                private_json(ROOT / 'data' / 'autonomous' / filename, account)
        for filename, checkpoint in output.get('checkpoints',{}).items():
            # Constrain untrusted remote output to local private state filenames.
            name = Path(filename).name
            if name == filename and name.endswith('.checkpoint.json'):
                private_json(ROOT/'data'/'autonomous'/name,checkpoint)
        report = output.get('report') or {name.removesuffix('.checkpoint.json'): value.get('result', {'status': value.get('status', 'interrupted')}) for name, value in output.get('checkpoints', {}).items()}
        report = {name: {k:v for k,v in result.items() if k not in {'last_observation','agent_actions'}} for name,result in report.items()}
        report['cloud_runtime'] = {'provider':'apify','status':run['status'],'actor_id':self.state['actor_id'],'run_id':run['id'],'usage':output.get('usage',{}), 'platform_cost_usd': run.get('usageTotalUsd')}
        private_json(ROOT/'data'/'registration_report.json',report)
        return report

    async def run(self, *, goal='Register developer accounts and retrieve API keys autonomously'):
        existing_run = self.state.get('run_id') if self.state.get('goal') == goal else None
        if existing_run:
            previous = await self.client.run(existing_run).get()
            previous = mapping(previous)
            if previous and previous['status'] in {'RUNNING','READY'}:
                self.record(status='resuming_active_run')
                run = previous
            else:
                run = None
        else:
            run = None
        if run is None:
            actor_id = await self.prepare()
            run = await self.client.actor(actor_id).start(run_input={'goal':goal},memory_mbytes=1024,run_timeout=timedelta(minutes=10),max_total_charge_usd=Decimal('0.25'),restart_on_error=False,wait_for_finish=1)
            run = mapping(run)
            self.record(run_id=run['id'],goal=goal,status='running')
        for _ in range(44):
            run = await self.client.run(run['id']).get()
            run = mapping(run)
            self.record(run_status=run['status'])
            if run['status'] in {'SUCCEEDED','FAILED','ABORTED','TIMED-OUT'}:
                return await self.import_output(run)
            await asyncio.sleep(15)
        await self.client.run(run['id']).abort()
        self.record(status='aborted_deadline')
        return {'runtime':{'status':'cloud_deadline_exceeded'}}
