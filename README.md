<div align="center">

<img src="assets/traceloc-logo.svg" alt="TraceLoc Logo" width="100%" />

# 🛰️ TraceLoc
### *Open-Source Intelligence para Endereços e Telefones*

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![C](https://img.shields.io/badge/C-Native-00599C?style=for-the-badge&logo=c&logoColor=white)
![C++](https://img.shields.io/badge/C%2B%2B-Native-00599C?style=for-the-badge&logo=cplusplus&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Cache-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-Educational%2FResearch-orange?style=for-the-badge)

</div>

---

## ✨ Visão Geral

**TraceLoc** é uma ferramenta OSINT para **correlação e enriquecimento** de dados de:
- 📍 **Endereços físicos** (geolocalização aproximada)
- 📞 **Números de telefone** (validação e metadados)

A solução foi desenhada para ser:
- **rápida**, com aceleração nativa opcional em C/C++
- **resiliente**, com fallback em Python e fallback offline determinístico
- **econômica**, com cache local SQLite e TTL configurável

---

## 🧠 Como funciona

O fluxo operacional do TraceLoc é:
1. Recebe alvo via CLI (`-a`, `-p` ou `-f`).
2. Consulta cache SQLite para evitar chamadas repetidas.
3. Executa módulo de endereço ou telefone.
4. Tenta caminho nativo (quando presente).
5. Faz fallback para implementação Python.
6. Em geocoding, se rede/API falhar, gera fallback offline determinístico.
7. Retorna resultado em `pretty` (padrão), `human`, `json` ou `csv`.

---

## 🧩 Arquitetura

```text
┌─────────────────────────────────────────────────────────────┐
│                        TraceLoc Core                        │
├─────────────────────────────────────────────────────────────┤
│                      CLI Interface (Python)                 │
├───────────────┬───────────────────────────────┬─────────────┤
│ Address Module│         Phone Module          │ Output      │
│ (C + Python)  │       (C++ + Python)          │ Formatters  │
├───────────────┼───────────────────────────────┼─────────────┤
│ Nominatim/API │ Carrier/Pattern Validation    │ JSON/CSV    │
│ Offline Fallback                               │ Human       │
└───────────────┴───────────────────────────────┴─────────────┘
                           │
                     SQLite Cache (TTL)
```

### Componentes

- **Core Orchestrator (Python)**: coordena CLI, módulos e estratégia de fallback.
- **Address Geo Engine (C)**: caminho nativo para geocoding OSM via `libcurl`.
- **Phone Intelligence Engine (C++)**: módulo nativo com base de países/carrier.
- **Cache Manager (SQLite)**: persistência local para reduzir chamadas externas.

---

## 📂 Estrutura do Projeto

- `traceloc.py` → CLI principal, cache, geocoding, phone-intel e formatadores.
- `libaddressgeo.c` → biblioteca nativa de geocoding.
- `libphoneintel.cpp` → biblioteca nativa de phone-intel.
- `assets/traceloc-logo.svg` → identidade visual oficial do projeto.
- `docs/terminal-demo-theme.sh` → tema para demos no terminal.
- `docs/ROADMAP.md` → roadmap visual do projeto.

---

## ⚙️ Instalação e Build

### Pré-requisitos

- Python 3.8+
- GCC / G++
- `libcurl` dev

### Build das bibliotecas nativas

```bash
gcc -shared -O3 -fPIC libaddressgeo.c -o libaddressgeo.so -lcurl
g++ -shared -O3 -std=c++11 -fPIC libphoneintel.cpp -o libphoneintel.so
```

> Se as bibliotecas nativas não estiverem disponíveis, o TraceLoc continua funcionando com fallback em Python.

---

## 🚀 Como Usar

### 1) Geocodificar um endereço

```bash
python3 traceloc.py -a "1600 Amphitheatre Parkway, Mountain View, CA" --format json
```

### 2) Analisar um telefone

```bash
python3 traceloc.py -p "+14155552671" --format json
```

### 3) Processar arquivo (entradas mistas)

```bash
python3 traceloc.py -f input.txt --format pretty
```

### 4) Salvar saída

```bash
python3 traceloc.py -f input.txt --format csv -o resultados.csv
```

---

## 🛡️ Estratégia de Resiliência

Para geocoding de endereço, o TraceLoc usa esta ordem:
1. **Native C geocoder** (se disponível)
2. **HTTP Python (`urllib`)**
3. **Fallback offline determinístico** (sem rede)

Resultado: o comando não quebra quando API externa está fora.

---



## 🖥️ Saída Visual (Pretty)

O formato padrão agora é `pretty`, pensado para uso em terminal:

- caixas visuais por resultado
- destaque para chaves importantes
- marcação especial para `warning` e `error`
- melhor legibilidade em demos e uso diário

Exemplo:

```bash
python3 traceloc.py -p 5511912669509
```

---

## 📞 Inteligência Telefônica (melhorada)

O módulo de telefone agora entrega resultado útil mesmo sem API paga:

- detecção de **tipo de linha** (ex.: `mobile`, `fixed_line`)
- **estimativa de localização** para números do Brasil via DDD
- **heurística de operadora** para prefixos móveis brasileiros comuns
- uso opcional do módulo nativo C++ para validação e carrier hints

> Se a API online (`numverify`) estiver configurada, os dados são enriquecidos e sobrescrevem heurísticas locais.

---
## 🎛️ Tema de Terminal para Demonstrações

Carregue o tema oficial TraceLoc:

```bash
source docs/terminal-demo-theme.sh
```

O script aplica:
- prompt estilizado TraceLoc
- paleta ciano/verde para demos
- aliases prontos (`tl-help`, `tl-phone`, `tl-addr`, `tl-mix`)

---

## 🗺️ Roadmap Visual

Consulte o roadmap completo em:

- [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## 💾 Cache SQLite

- Banco em: `/tmp/traceloc_cache/geocache.db`
- TTL padrão: **30 dias**
- Vantagens: menos latência, menos chamadas externas, maior estabilidade operacional

---

## 📤 Formatos de Saída

- `--format pretty` (visual aprimorado com caixas e destaque de campos)
- `--format human` (texto simples)
- `--format json` (integrações/API)
- `--format csv` (planilhas e BI)

---

## ⚠️ Aviso Legal

Uso destinado a **pesquisa, educação e análise autorizada**.
Você é responsável por cumprir leis locais, políticas de provedores e termos de APIs utilizadas.

---

## 👤 Autor

**João Pedro**
