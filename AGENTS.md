# AGENTS.md

Guia de contexto para agentes de IA que trabalham neste repositório.
Leia este arquivo antes de alterar qualquer coisa.

---

## 1. O que é este projeto

**Little Backup Box** transforma um Raspberry Pi (Raspberry Pi OS **Trixie**) num hub de
backup portátil para fotógrafos e viajantes. Copia arquivos de câmeras, cartões, celulares
e discos USB para armazenamento local, NVMe, servidores rsync, nuvens (via rclone) e redes
sociais. É controlado por web UI, por um display OLED com botões físicos, ou roda totalmente
automático no boot.

- **Upstream:** `outdoorbits/little-backup-box` (autor: Stefan Saam; projeto original de
  Dmitri Popov). Licença **GPLv3**.
- **Este repositório:** `eacarva/little-backup-box` — fork de trabalho.
- **Plataforma alvo:** Raspberry Pi OS Trixie (`main`). Bookworm é mantido apenas na branch
  `bookworm` do upstream; o instalador redireciona automaticamente quando detecta OS 12.

---

## 2. Arquitetura em 4 camadas

### Camada 1 — Instalador (`install-little-backup-box.sh`, ~23 KB)

É o coração operacional. O **mesmo script serve de instalador e de atualizador**, decidido
pela variável `SCRIPT_MODE` (`install` ou `update`, definida pela existência de
`/var/www/little-backup-box`). Toda alteração feita nele precisa funcionar nos dois modos.

O que ele faz:
- Detecta a versão do OS: 13 (Trixie) segue; 12 (Bookworm) redireciona para a branch
  `bookworm`; qualquer outra aborta.
- Instala ~50 pacotes apt (rsync, gphoto2, exiftool, php-fpm, samba, proftpd, imagemagick,
  ffmpeg, openvpn, wireguard, f3, sqlite3, …) e pacotes pip (`atproto`, `Mastodon.py`).
- Copia `scripts/` para `/var/www/little-backup-box` (o `const_WEB_ROOT_LBB`).
- Configura Apache (mpm_event + php-fpm; HTTP 80/8080 e HTTPS 443 com certificado
  autoassinado), Samba, proftpd e o hostname `lbb`.
- Reescreve o crontab do root do zero:

```
@reboot  backup-autorun.py      # backup automático no boot
@reboot  start-rclone-gui.py
* * * * *  cron_ip.sh           # exibe / envia o IP
* * * * *  cron_idletime.py     # desliga por ociosidade
```

Scripts satélites na raiz: `install-comitup.sh` (hotspot WiFi), `install-tinyfilemanager.sh`,
`setup-graphical-environment.sh`, `setup-firefox.sh`, `install-firefox-keyboard.sh`
(modo quiosque em touchscreen), `set_locale.sh`, `prefer-ipv4-eth0.sh`.

### Camada 2 — Motor de backup (Python, `scripts/`)

`backup.py` (~73 KB, uma classe `backup`) é o orquestrador. Interface por CLI, com um
vocabulário fixo de origens e destinos:

- **Origens:** `anyusb`, `usb`, `internal`, `nvme`, `camera`, `cloud:<serviço>`,
  `cloud_rsync`, `ftp` — mais as "funções" `thumbnails`, `database`, `exif`, `rename`,
  que rodam etapas isoladas sem copiar nada.
- **Destinos:** `usb`, `internal`, `nvme`, `cloud:<serviço>`, `cloud_rsync`,
  `social:telegram|mastodon|bluesky|matrix`.

Suporta **backup secundário encadeado** (`--SecSourceName` / `--SecTargetName`),
tipicamente disco local → nuvem. Quando isso acontece, a geração de thumbnails é deslocada
para a fase de upload (`shiftGenerateThumbnails`), para aproveitar o tempo de rede.

Fluxo de `run()`:

```
monta destino
  → loop sobre origens dinâmicas (cada USB / câmera conectada, uma a uma)
  → sync   (rsync entre locais · rclone para nuvem · gphoto2 para câmera)
  → rename (por data EXIF)
  → syncDatabase  (SQLite do View)
  → updateEXIF
  → generateThumbnails
  → finish (relatório, e-mail, desligar)
```

Argumentos booleanos aceitam três estados: `'True'`, `'False'` e `'setup'` — este último
significa "use o valor do `config.cfg`". Preserve esse padrão ao adicionar opções.

Bibliotecas de apoio, cada uma com responsabilidade bem delimitada:

| Arquivo | Papel |
|---|---|
| `lib_storage.py` (~50 KB) | Detecção, montagem, UUID/ID de dispositivos, partições, câmeras gphoto2 |
| `lib_setup.py` | Configuração tipada: ~110 chaves `conf_*` com tipo e default, persistidas em `config.cfg` |
| `lib_backup.py` | `progressmonitor` (parse da saída de rsync/rclone) e `reporter` (e-mail e resumo) |
| `lib_view.py` | Banco SQLite `images.db`: EXIF, rating, comentários |
| `lib_socialmedia*.py` | Classe-pai + Telegram, Mastodon, Bluesky, Matrix |
| `lib_display.py`, `display.py`, `displaymenu.py` | OLED SSD1306 / SPI, statusbar, menu por botões GPIO |
| `lib_mail.py`, `lib_vpn.py`, `lib_network.py`, `lib_comitup.py`, `lib_password.py`, `lib_git.py`, `lib_clean.py`, `lib_poweroff.py`, `lib_proftpd.py`, `lib_metadata.py` | Serviços auxiliares |

`scripts/constants.sh` é **compartilhado entre bash, Python e PHP** — cada linguagem faz seu
próprio parse do mesmo arquivo. Contém caminhos, timeouts, mountpoints e as listas de
extensões (RAW, HEIC, vídeo, áudio, texto). Ao adicionar uma constante, lembre que os três
parsers vão lê-la.

### Camada 3 — Web UI (PHP, `scripts/*.php`)

Sem framework: PHP procedural + Bootstrap 5 (vendorizado em `scripts/css` e `scripts/js`).

| Arquivo | Papel |
|---|---|
| `index.php` | Tela principal; dispara `backup.py` em background |
| `setup.php` (~104 KB) | Todas as configurações |
| `view.php` (~61 KB) | Visualizador de mídia: rating por estrelas, lupa, slideshow, publicação em redes sociais |
| `tools.php` + `cmd.php` | Operações destrutivas (formatar, fsck, f3probe, update) — exigem senha e rodam em background com log ao vivo |
| `frame.php`, `sub-*.php` | Includes: menu, footer, ícones SVG, logmonitor, popups |

**i18n:** `i18n.class.php` compila os JSON de `scripts/lang/` numa classe com constantes
(`L::main_usb_button`). Os JSON são aninhados e a chave é achatada com underscore:
`box.backup.primary` vira `box_backup_primary`. O Python acessa as mesmas chaves via
`lib_language.py` (`lan.l('box_backup_primary')`).
**Toda string nova precisa ser adicionada nos 4 idiomas: `en`, `de`, `es`, `fr`.**

### Camada 4 — Hardware e rede

Display OLED com menu navegável por botões físicos (mapeamento em `scripts/buttons.cfg`),
comitup para hotspot WiFi, detecção de captive portal (`portal_page_detector.py` — a feature
mais recente, ainda alpha), calibração de touchscreen (`touch_cal_web.py`,
`kiosk-calibrate.sh`) e os LEDs do Raspberry Pi usados como indicadores de estado.

---

## 3. Três coisas críticas ao trabalhar neste fork

### 3.1 O auto-update aponta para o upstream, não para este fork

O repositório `outdoorbits/little-backup-box` está hardcoded em 5 pontos:

- `scripts/lib_git.py` — checagem de versão via API do GitHub
- `scripts/cmd.php` — comandos `update` e `update_development`
- `install-little-backup-box.sh` — `git clone` e o redirecionamento para Bookworm

**Consequência:** se você instalar esta versão numa box e clicar em "Update" na web UI,
o código do upstream sobrescreve as alterações do fork. Para um fork instalável de verdade,
esses pontos precisam apontar para `eacarva/little-backup-box`.

### 3.2 O modelo de segurança pressupõe rede confiável

- `etc/sudoers_d_www-data` contém `www-data ALL=(ALL) NOPASSWD:ALL` — o servidor web tem
  root irrestrito.
- `cmd.php` monta linhas de comando por concatenação de string e executa via `sh -c`.
- `lib_password.py` interpola a senha em comandos com `shell=True`.
- As senhas ficam em texto plano em `config.cfg`.

Isso é uma decisão consciente do projeto (dispositivo de campo, isolado, operado pelo dono).
Vale saber: **esta box não deve ser exposta à internet aberta**. Não "conserte" isso de
passagem — é uma mudança de arquitetura, não um bug isolado; converse antes.

### 3.3 Não existe suíte de testes

O único CI é CodeQL (JavaScript e Python), em `main` e em pull requests
(`.github/workflows/codeql-analysis.yml`). Não há testes unitários, linter nem formatador.

Portanto: **nenhuma alteração é validável neste repositório sozinho.** O que dá para fazer
sem hardware é conferência estática — `python3 -m py_compile scripts/*.py`,
`php -l scripts/<arquivo>.php`, `bash -n <script>.sh`. Validação real exige um Raspberry Pi.
Diga isso com clareza ao relatar o trabalho, em vez de afirmar que "está funcionando".

---

## 4. Convenções de código

Imite o código ao redor. O estilo do upstream é consistente e deliberado:

- **Indentação com tabs**, em Python, PHP e shell.
- Atribuições alinhadas com tabs (`self.SourceName<TAB><TAB>= SourceName`).
- Python: métodos privados com `__` (name mangling), objetos de lib guardados em
  `self.__setup`, `self.__display`, `self.__log`, `self.__lan`.
- Comentários escassos — o código do upstream quase não comenta. Não encha de comentário.
- Mensagens de commit em inglês, minúsculas, no estilo do upstream:
  `bugfixes: Comitup reset and View`, `add button config for Waveshare 1.44inch LCD HAT`.
- Nada de reformatação em massa: mantém o diff legível contra o upstream.

---

## 5. Fluxo de git neste fork

- O clone é **raso** (`--depth`), com 56 commits. `git log` completo não está disponível.
- Não há remote do upstream configurado — só `origin` (`eacarva/little-backup-box`).
- Desenvolva na branch designada da sessão, nunca direto na `main`, para manter a `main`
  alinhada com o upstream e facilitar rebases futuros.
- Não abra pull request sem pedido explícito.

---

## 6. Mapa de diretórios

```
/
├── install-little-backup-box.sh    instalador + atualizador (ponto de entrada)
├── install-comitup.sh              hotspot WiFi
├── install-tinyfilemanager.sh      gerenciador de arquivos web
├── setup-*.sh, set_locale.sh       ambiente gráfico, firefox, locale
├── README.md, changelog.md         também servem de site GitHub Pages (_config.yml, CNAME)
├── etc/                            configs de sistema (apache, samba, proftpd, sudoers)
├── scripts/                        → copiado para /var/www/little-backup-box
│   ├── backup.py                   orquestrador de backup
│   ├── backup-autorun.py           backup automático no boot
│   ├── lib_*.py                    bibliotecas Python
│   ├── *.php                       web UI
│   ├── sub-*.php                   includes de UI
│   ├── constants.sh                constantes compartilhadas (bash + python + php)
│   ├── buttons.cfg                 mapeamento dos botões do display
│   ├── lang/                       en, de, es, fr (JSON)
│   ├── css/, js/, img/             assets (Bootstrap vendorizado)
│   ├── mods/                       scripts opcionais (update_libraw.sh)
│   └── tmp/                        runtime: log, lockfiles, conteúdo do display
└── .github/workflows/              CodeQL
```

---

## 7. Navegação econômica (leia antes de abrir arquivos)

Este repositório tem poucos arquivos, mas vários são enormes. Abrir um deles inteiro
consome uma fatia grande do contexto e quase nunca é necessário.

**Arquivos grandes — nunca leia por inteiro, use `grep -n` e depois `sed -n 'A,Bp'`:**

| Arquivo | Tamanho | Como navegar |
|---|---|---|
| `scripts/setup.php` | ~102 KB | `grep -n 'conf_<CHAVE>'` para achar o campo do formulário |
| `scripts/backup.py` | ~71 KB | `grep -nP '^\tdef '` lista os métodos da classe `backup` |
| `scripts/view.php` | ~60 KB | `grep -n 'function \|case '` |
| `scripts/lib_storage.py` | ~49 KB | `grep -nP '^\tdef \|^def '` |
| `scripts/lang/*.json` | ~45–50 KB cada | `grep -n '"<chave>"'`; use `en.json` como referência |
| `scripts/cmd.php` | ~22 KB | `grep -n "case '"` lista os comandos |

**Nunca leia** (vendorizados ou binários, sem valor para o trabalho; já bloqueados por
`Read` em `.claude/settings.json`): `scripts/css/bootstrap*.css`, `scripts/js/bootstrap*.js`,
`scripts/favicon.ico`, `scripts/img/**`.

**Padrões que resolvem a maioria das buscas em uma chamada:**

```bash
grep -nP '^\tdef |^def |^class ' scripts/<arquivo>.py   # mapa de um módulo Python
grep -n "case '"                 scripts/cmd.php        # comandos da web UI
grep -rn 'conf_<CHAVE>' scripts/                        # onde uma config é lida/escrita
grep -n '<chave>' scripts/lang/en.json                  # string de i18n
grep -rn 'outdoorbits' --include='*.py' --include='*.php' --include='*.sh' .
```

**Verificação estática (não precisa de Raspberry Pi):**

```bash
python3 -m py_compile scripts/*.py
for f in scripts/*.php; do php -l "$f"; done
bash -n install-little-backup-box.sh
```

**Regra geral:** localize com `grep -n`, leia só a faixa de linhas relevante, e prefira
`git diff` a reler o arquivo depois de editar.
