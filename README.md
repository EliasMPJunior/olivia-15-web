# Olívia 15 · Presenças

Servidor Django com SQLite e área do convidado dentro do Django Admin. O visual usa azul-marinho, prata, os logos e uma versão discreta do cenário do convite. O protótipo anterior foi preservado em `legacy/index.html`.

## Executar com Docker

Na pasta `web`:

```sh
./up.sh
```

Abra **http://localhost:8001/**. A raiz leva a `/admin/`; o cadastro público está em `/cadastro/` e também em `/admin/cadastro/`.

Na primeira inicialização, o Docker cria automaticamente uma conta administrativa, como no `brasibim`. No desenvolvimento, os padrões são:

- **Telefone:** `+5524999999999` (também aceita `24999999999` no login).
- **Senha:** `admin`.

As variáveis `DJANGO_ADMIN_PHONE`, `DJANGO_ADMIN_PASSWORD` e `DJANGO_ADMIN_NAME` permitem personalizar essa conta. Se já houver um superusuário ativo, a inicialização não altera sua senha nem cria outra conta. Contas comuns existentes não impedem a criação do primeiro administrador, mas nunca são promovidas automaticamente.

Em produção, telefone e senha devem ser definidos explicitamente no `.env`; não há senha padrão. Para criar outra conta administrativa manualmente, continua disponível:

```sh
docker compose -f docker/docker-compose.yml exec olivia python manage.py createsuperuser
```

A infraestrutura segue o formato de `brasibim`: `src/`, Dockerfile, Compose, `up.sh`, migrações e endpoint de saúde. Não usa PostgreSQL, S3 ou Redis. O SQLite fica em `/data/db.sqlite3`, persistido no volume `olivia15_olivia_data`. Não execute `docker compose down -v` se quiser manter os dados.

## Executar sem Docker

Python 3.13 recomendado:

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r src/requirements.txt
DJANGO_DEBUG=1 .venv/bin/python src/manage.py migrate
DJANGO_DEBUG=1 .venv/bin/python src/manage.py runserver 127.0.0.1:8001
```

Para superusuário local:

```sh
DJANGO_DEBUG=1 .venv/bin/python src/manage.py createsuperuser
```

O SQLite local fica em `src/db.sqlite3` e é independente do banco do Docker.

## Cadastro e privacidade

- Cadastro de acesso com nome, telefone com DDD, senha e confirmação. Ele exige um responsável ativo previamente cadastrado pela organização ou pela importação. Nome e telefone devem corresponder à mesma conta; caso contrário, retorna “Pessoa não cadastrada”. Não cria contas ou famílias novas.
- Conforme definido, **informar o telefone é suficiente**: não há SMS, WhatsApp, código ou verificação de posse. O sistema não apresenta o telefone como verificado.
- O login usa telefone e senha. Números brasileiros com ou sem formatação são normalizados com `+55`; números internacionais devem começar com `+`.
- Cada conta pertence a um responsável da família. A model `Family` é criada automaticamente para esse responsável; a model `Guest` contém os familiares, sem telefone, senha ou conta. Cada responsável tem sua própria resposta de presença e a lista da sua família. Cada pessoa pode estar pendente, confirmada ou não comparecer. As respostas podem ser alteradas.
- A lista, pesquisas, formulários, histórico, exclusão e ações em lote são filtrados pelo responsável. Saber o UUID de outro convidado não permite consultá-lo ou modificá-lo.
- Os convidados são registros da lista, não novas contas; cadastrar alguém não envia convites nem cria senhas. Apenas o superusuário inclui, edita ou remove esses registros. O responsável consulta sua família e altera somente as respostas de presença.
- A família do convidado é automática para contas comuns. Para superusuários, escolher outra família é opcional. O cadastro de família permite adicionar vários familiares por nome e presença, sem pedir telefone. Criar outro responsável é uma operação separada, que cria outra conta e outra família.
- Superusuários têm visão administrativa de todas as listas e contas. Uma conta comum não consegue administrar usuários ou permissões.
- Perfil e troca de senha ficam na navegação do Admin. O telefone fica apenas para consulta no perfil do responsável; somente o superusuário pode alterá-lo. Sair é uma ação POST protegida por CSRF.
- Tentativas de login e cadastro têm limites por IP persistidos no banco, compartilhados entre os processos. Não são usados serviços externos.

## Produção

Django não executa no GitHub Pages. Publique este servidor em um host com Docker e HTTPS, mantendo o convite estático no domínio atual. O botão de confirmação do convite pode depois apontar para a URL deste servidor; este trabalho não altera o site em produção.

Copie `.env.example` para `.env` e defina uma chave aleatória, o domínio e a origem HTTPS. Exemplo de geração de chave:

```sh
.venv/bin/python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

Inicie explicitamente com o arquivo de produção:

```sh
docker compose --env-file .env -f docker/docker-compose.prod.yml up -d --build --wait
```

Configure um proxy HTTPS para `127.0.0.1:8001`, passando `Host`, definindo `X-Forwarded-Proto: https` e sobrescrevendo `X-Forwarded-For` com o IP real do visitante. A porta da aplicação só é publicada em loopback. O proxy deve sobrescrever esses cabeçalhos recebidos do visitante. O IP encaminhado é usado nos limites de tentativas, evitando que todos os visitantes compartilhem o limite do proxy. `DJANGO_TRUST_PROXY=1` habilita a confiança nesse cabeçalho. `DJANGO_HEALTH_HOST` precisa corresponder a um dos `DJANGO_ALLOWED_HOSTS`.

O container de produção executa como usuário sem privilégios, aplica migrações, garante a conta administrativa inicial, coleta estáticos e inicia Gunicorn com um worker e quatro threads. WhiteNoise entrega os estáticos com hash e compressão. O banco persiste no mesmo volume nomeado. HTTPS, cookies seguros e proteção CSRF ficam habilitados em produção. HSTS se aplica apenas ao domínio servido, sem impor regras aos demais subdomínios.

Variáveis principais:

| Variável | Finalidade |
|---|---|
| `DJANGO_DEBUG` | `1` apenas no desenvolvimento |
| `DJANGO_SECRET_KEY` | Obrigatória em produção |
| `DJANGO_ALLOWED_HOSTS` | Domínios permitidos, separados por vírgula |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origens HTTPS autorizadas |
| `DJANGO_DB_PATH` | Caminho do SQLite; no container, `/data/db.sqlite3` |
| `DJANGO_TRUST_PROXY` | Confia no protocolo e no IP definidos pelo proxy controlado |
| `DJANGO_HEALTH_HOST` | Host usado na verificação do container em produção |
| `OLIVIA_PORT` | Porta local publicada, padrão `8001` |
| `INVITATION_URL` | Retorno ao menu estático, padrão `https://olivia.brasidata.com.br/menu.html` |

O endpoint `/api/health/` faz uma leitura simples do banco. Não expõe contas ou listas.

## Backup do SQLite

Faça backup consistente pelo mecanismo de backup do SQLite, sem copiar um arquivo em escrita. Por exemplo, com o container em execução:

```sh
docker compose -f docker/docker-compose.yml exec olivia python -c 'import sqlite3; source=sqlite3.connect("/data/db.sqlite3"); target=sqlite3.connect("/data/backup.sqlite3"); source.backup(target); target.close(); source.close()'
docker compose -f docker/docker-compose.yml cp olivia:/data/backup.sqlite3 ./backup.sqlite3
```

Esse arquivo contém dados pessoais e não deve ser versionado.

## Verificação

```sh
DJANGO_DEBUG=1 .venv/bin/python src/manage.py check
DJANGO_DEBUG=1 .venv/bin/python src/manage.py makemigrations --check --dry-run
DJANGO_DEBUG=1 .venv/bin/python src/manage.py test guests --settings=config.test_settings
```

Os testes usam um banco isolado em memória. Cobrem cadastro, telefone, senha, CSRF, privacidade em todas as rotas, propriedade dos registros, ações em lote, perfil, superusuários e presenças. As telas usam templates e formulários do Admin com tema próprio; o painel inicial é uma visão simplificada sobre os mesmos modelos.

## Famílias

A estrutura é `Responsável (User, telefone e senha) → Família (Family) → Convidados (Guest, nome e presença)`. O responsável já representa a si próprio e não precisa se adicionar como convidado.

Na organização, cadastre um responsável e você será direcionado à família para adicionar os demais convidados. O responsável pode consultar “Ver minha família” e responder às presenças. Apenas o superusuário pode adicionar, editar ou remover os convidados, inclusive na lista dentro da família. Apenas a organização pode visualizar todas as famílias; cada responsável vê somente a sua.

A migração `0003_family` cria uma família por conta existente e preserva nomes, presenças e datas dos convidados ao transferir os vínculos anteriores. Um backup do banco Docker anterior à migração foi preservado em `/data/pre-family.sqlite3`.

## Importar a lista de convidados

A lista está em `src/data/convidados.json`. Cada `principal` vira uma conta de responsável e uma família; os `guests` viram convidados dessa família, sem criar outras contas. Tratamento, nome e sobrenome são reunidos no nome de exibição. Telefones dos convidados, quando informados, são preservados em um campo opcional.

Faça primeiro uma simulação no banco do Docker:

```sh
docker compose -f docker/docker-compose.yml exec olivia python manage.py migrate
docker compose -f docker/docker-compose.yml exec olivia python manage.py import_convidados --dry-run --report /tmp/importacao-convidados.json
```

Para importar de fato:

```sh
docker compose -f docker/docker-compose.yml exec olivia python manage.py import_convidados
```

Também existe um script Python direto, para o banco local:

```sh
DJANGO_DEBUG=1 .venv/bin/python src/import_convidados.py --dry-run
DJANGO_DEBUG=1 .venv/bin/python src/import_convidados.py
```

É possível informar outro arquivo como argumento, além de `--report caminho.json` e `--strict`. O modo `--strict` desfaz toda a importação se algum grupo estiver inválido; por padrão, os grupos inválidos são pulados e relatados, e os demais são importados. `--dry-run` sempre desfaz todas as alterações.

Reexecutar a importação não duplica os registros: responsáveis são identificados pelo telefone normalizado, e convidados pelo nome dentro da família, ignorando diferenças de caixa e espaços. Senhas, nomes e presenças existentes são mantidos. Um telefone de convidado já preenchido não é sobrescrito; apenas campos vazios são completados.

Principais sem telefone ou com telefone inválido ficam pendentes; corrija o JSON e execute novamente. Nenhum telefone é inventado. As novas contas são criadas **sem senha utilizável**, sem privilégios administrativos e com presença pendente. O responsável pode acessar `/cadastro/`, informar o nome e telefone cadastrados e definir sua senha. Também é possível ao superusuário definir a senha pelo Admin. O script não envia mensagens ou códigos.

O cadastro de acesso também permite substituir uma senha já definida, usando a mesma conferência de nome e telefone. A comparação do nome ignora diferenças de maiúsculas, acentos, espaços e tratamentos familiares iniciais (como Tia ou Vó), mas exige o restante do nome completo. Apenas a senha é atualizada: família, telefone, nome, presenças e permissões são preservados. Contas administrativas ou inativas não podem usar esse fluxo público.
