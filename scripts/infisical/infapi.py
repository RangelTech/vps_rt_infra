"""Cliente minimo da API do Infisical (login Universal Auth). Credencial lida de um arquivo FORA do repositorio
(INFISICAL_ENV_FILE; padrao: cofre pessoal em ~/.claude/secrets). Nunca grava nem imprime segredo."""
import json,os,urllib.request,re
def _env():
    env={}
    for l in open(os.environ.get('INFISICAL_ENV_FILE', os.path.expanduser('~/.claude/secrets/infisical-rt-automacao.env')),encoding='utf-8'):
        m=re.match(r'^([A-Z_]+)=(.*)$',l.rstrip('\r\n'))
        if m: env[m.group(1)]=m.group(2)
    return env
E=_env()
def call(path,body=None,tok=None,method=None):
    h={'User-Agent':'curl/8.5.0','Content-Type':'application/json'}
    if tok: h['Authorization']='Bearer '+tok
    r=urllib.request.Request(E['INFISICAL_URL']+path,data=json.dumps(body).encode() if body is not None else None,headers=h,method=method)
    try:
        return json.load(urllib.request.urlopen(r,timeout=30))
    except urllib.error.HTTPError as e:
        return {'erro':e.code,'corpo':e.read().decode()[:300]}
def token():
    a=call('/api/v1/auth/universal-auth/login',{'clientId':E['INFISICAL_CLIENT_ID'],'clientSecret':E['INFISICAL_CLIENT_SECRET']})
    return a['accessToken']
