# Redesenho da página de Configurações (`setup.php`)

Data: 2026-09-30 · Status: aprovado no brainstorming

## Problema

`setup.php` mostra ~19 blocos `<details>` empilhados, alguns com sanfonas dentro de
sanfonas, dentro de um form único de ~110 campos. Os campos não têm contêiner: são
`checkbox + label + <br> + texto solto + <strong>aviso</strong> + <br>`. O resultado é
difícil de navegar e de ler, no desktop e no celular.

## Decisões

- **Abordagem A — casca nova sobre o markup atual.** O `setup.php` quase não muda; a
  navegação vem de um JS novo e o visual do `lbb-fork.css`. Reescrever o HTML (B) ou
  gerar por esquema (C) foi descartado: o diff enorme contra o upstream vira conflito
  em todo sync.
- **Navegação A (escolhida no companion):** menu lateral agrupado no desktop; no
  celular, lista de categorias → tela da seção.
- Os dois tamanhos importam igualmente.

## 1. Estrutura e navegação

Arquivos:

- `scripts/js/setup-nav.js` (novo, ~80 linhas).
- `scripts/css/lbb-fork.css`: bloco novo "Settings navigation"; saem as regras
  `form > .card:has(...) { order: N }` e `form:has(> .card #conf_LANGUAGE)`, que o
  menu substitui.
- `scripts/setup.php`: inclui o script e emite os textos traduzidos
  (`json_encode`) num `data-` ou objeto global. Nada mais muda no markup.
- `scripts/lang/{de,en,es,fr,pt}.json`: chaves novas (seção 3).

Identificação dos blocos (cada `.card` de topo com `details`), pelo campo que contém —
mesmo padrão das regras de ordem atuais:

| Grupo | Seção | Seletor dentro do card | hash |
|---|---|---|---|
| Uso | Backup | `#conf_BACKUP_CHECKSUM` | `backup` |
| Uso | Idioma e fuso | `#conf_LANGUAGE` | `language` |
| Uso | Aparência | `#conf_THEME` | `appearance` |
| Uso | Visualizador View | `#conf_BACKUP_GENERATE_THUMBNAILS` | `view` |
| Box | Display | `#conf_DISP_OLD` | `display` |
| Box | Menu do display | `#conf_MENU_ENABLED` | `menu` |
| Box | Energia | `#conf_POWER_OFF_IDLE_TIME` | `energy` |
| Box | Hardware | `#conf_FAN_PWM_TEMP_C` | `hardware` |
| Rede e nuvem | Wi-Fi | `#conf_WIFI_PASSWORD_TYPE` | `wifi` |
| Rede e nuvem | VPN | `#conf_VPN_TYPE_RSYNC` | `vpn` |
| Rede e nuvem | Nuvem | `#restart_rclone_gui` | `cloud` |
| Rede e nuvem | rsync | `#conf_RSYNC_SERVER` | `rsync` |
| Rede e nuvem | Comitup (se instalado) | `a[href*="CMD=comitup_reset"]` | `comitup` |
| Avisos | E-mail | `#conf_MAIL_NOTIFICATIONS` | `mail` |
| Avisos | Redes sociais | `#conf_SOCIAL_PUBLISH_DATE` | `social` |
| Sistema | Senha | `#conf_PASSWORD_1` | `password` |
| Sistema | Depuração | `#conf_LOGLEVEL` | `debug` |
| Sistema | Exportar / importar | `#settings_file` | `settings-file` |
| Sistema | Atualização | `[onclick*="CMD=update'"]` | `update` |
| Sistema | Sair da LBB (se houver startx) | `[name="exit_lbb"]` | `exit` |

- O rótulo de cada item do menu é o texto do `summary` do bloco (já traduzido).
- Card de topo com `details` que não casar com nenhum seletor vai para o grupo
  "Outros" no fim do menu, com hash `section-N` — seção nova do upstream nunca some.
- **Nenhum card muda de lugar dentro do DOM em relação ao form.** O JS cria
  `<div class="settings">` com `<nav class="settings-nav">` e `<div class="settings-main">`
  e move para dentro dele o `<form>` principal inteiro e os cards irmãos que vêm depois
  dele (mesma ordem). Cards dentro do form continuam dentro; forms próprios (importar,
  sair) continuam intactos. O POST não muda.
- A seção ativa recebe `open`; as demais ficam com a classe `settings-hidden`
  (`display: none`). Os cards de `$SetupMessages` (acima do form) ficam onde estão.
- **Estado:** a seção ativa vive no hash (`setup.php#backup`); `hashchange` troca de
  seção, então o voltar do navegador funciona. A última seção vai para
  `sessionStorage` (em `try/catch`) para voltar a ela depois do POST, que perde o hash.
- **Desktop (≥ 700px):** grid `nav | main`, nav `position: sticky`. Sem hash e sem
  seção lembrada → Backup.
- **Celular (< 700px):** sem hash → só a lista de categorias (itens grandes, "›").
  Com hash → só a seção, com botão "‹ Configurações" no topo que limpa o hash.
- **Sem JS:** a página é a de hoje (sanfonas). O CSS novo fica todo sob `.settings`,
  que só existe quando o JS roda.

## 2. Visual dos campos (sem reescrever markup)

Tudo escopado em `.settings-main`:

- **Checkbox → interruptor** com `appearance: none` no próprio `input[type=checkbox]`;
  `label for` e teclado continuam funcionando. Foco visível (`:focus-visible`).
- **Texto solto → ajuda:** o JS percorre os nós de texto não vazios que são filhos
  diretos do `details` da seção (e de `div`s diretos sem classe) e os embrulha em
  `<span class="help">` (cinza, menor). Os `<br>` desses mesmos níveis ficam
  `display: none`; espaçamento vem do CSS (`.help` e `strong` viram `display: block`).
- **`<strong>` de aviso** (filho direto do mesmo nível) → linha âmbar (`--canyusb`) com
  "⚠", peso normal.
- **`h3`/`h4` de grupo** → subtítulo pequeno em maiúsculas (`--font-label`) com linha
  divisória acima (exceto o primeiro).
- **`details` aninhados** → o JS define `open`; o CSS esconde o "+/−" e desliga o
  clique no `summary` (vira subtítulo).
- **select / input / textarea** → mesma altura mínima (44px), borda `--cline`, raio
  10px; `width: 100%` abaixo de 700px.
- Layout empilhado (rótulo → controle → ajuda). Lado a lado ficou fora de escopo: exige
  markup por campo.

## 3. Salvar e alterações não salvas

- A barra fixa atual (`.card[style*="sticky"]` com `button[name=save]`) ganha, à
  esquerda, um `<span class="settings-dirty">` criado pelo JS.
- Contagem: campos do form principal cujo valor atual difere do inicial
  (`defaultValue`, `defaultChecked`, `defaultSelected`), recalculada em `input` e
  `change`. `0` → "Nenhuma alteração" e botão com aparência apagada (continua
  clicável); `N` → "● N alterações não salvas" em âmbar. Desfazer volta a contagem.
  Campos `type=file` e `hidden` não contam.
- `beforeunload` com alterações pendentes → aviso nativo. O `submit` do form
  principal desliga o aviso.
- Seções fora do form (Exportar/importar, Atualização, Comitup, Sair) escondem a barra.
- Chaves novas em `config` nos 5 idiomas: `nav_group_use`, `nav_group_box`,
  `nav_group_network`, `nav_group_alerts`, `nav_group_system`, `nav_group_other`,
  `nav_back` ("Configurações"), `unsaved_none` ("Nenhuma alteração"),
  `unsaved_count` ("{n} alterações não salvas"; o JS troca `{n}`).

## 4. Testes

Sem suíte para PHP/JS; preview local (`dev/preview.sh`, Docker) mais um check
executável:

- **POST idêntico:** no preview, serializar o `FormData` do form principal com o JS
  desligado e ligado (`[...new FormData(form)]`) e comparar — nomes, ordem e valores
  iguais. O snippet fica documentado no plano.
- Todas as seções nos temas `light`, `dark` e `sepia`, em 1280px e 375px, com
  screenshot; procurar texto sem estilo, espaço faltando e campo cortado.
- Fluxos: trocar de seção mantém alterações; recarregar com pendência avisa; depois de
  salvar volta à mesma seção; voltar do navegador (lista ↔ seção no celular); sem JS a
  página continua como hoje.
- `php -l scripts/setup.php`; JSONs válidos (`python3 -m json.tool`).
- **Só na box:** salvar de verdade, senha Wi-Fi dinâmica, upload de VPN, calibração do
  touch, reiniciar interface do rclone.

## Riscos

- Embrulhar texto solto depende do markup do upstream; se mudar, o pior caso é texto
  sem o estilo cinza.
- `:has()` e `color-mix()` já são exigidos pelo fork hoje.

## Fora de escopo

- Reescrever textos de ajuda do upstream.
- Layout de campo lado a lado.
- Página do comitup (tarefa separada, depois desta).
