# Sala do Vereador (partelli.pro/vereador)

Painel de fiscalização para vereadores do Espírito Santo. Piloto: Ibatiba (análise completa). Demais municípios: bloco padronizado lido do portal da transparência (E&L, portaltp) de cada prefeitura.

- `index.html`: página (gerada a partir de partes; Ibatiba curado + seletor de município).
- `dados/`: arquivos de Ibatiba, mapa do ES (TCE-ES) e `dados/mun/<ibge>.json` (um por município, gerado pelo robô).
- `robo/coletar_municipios.py`: lê `/api/transparencia.asmx/json_*` de cada portal. Só dados públicos agregados, sem nomes de servidores e sem pessoas físicas.
- `.github/workflows/coletar.yml`: roda todo dia às 20h (Brasília) e também sob demanda (Actions > Run workflow, com lista opcional de municípios).

Publicação: conectar este repositório em Git na Hostinger (hPanel) com implantação automática para a pasta `vereador`. Página mantida oculta (noindex).
