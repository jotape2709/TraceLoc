<div align="center">

# 🛰️ TraceLoc
### *Open-Source Intelligence para Endereços e Telefones*

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![C](https://img.shields.io/badge/C-Native-00599C?style=for-the-badge&logo=c&logoColor=white)
![C++](https://img.shields.io/badge/C%2B%2B-Native-00599C?style=for-the-badge&logo=cplusplus&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Cache-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
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

## 🧠 Arquitetura

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
python3 traceloc.py -f input.txt --format human
```

### 4) Salvar saída

```bash
python3 traceloc.py -f input.txt --format csv -o resultados.csv
```

---

## 🛡️ Estratégia de Resiliência (Importante)

Para geocoding de endereço, o TraceLoc usa esta ordem:
1. **Native C geocoder** (se disponível)
2. **HTTP Python (`urllib`)**
3. **Fallback offline determinístico** (sem rede)

Isso garante que o comando **não quebra** mesmo sem internet/API.
No fallback offline, o resultado vem com:
- `resolution: "offline-deterministic-fallback"`
- `warning` explicando a indisponibilidade externa

---

## 💾 Cache SQLite

- Banco em: `/tmp/traceloc_cache/geocache.db`
- TTL padrão: **30 dias**
- Vantagens: menos latência, menos chamadas externas, maior estabilidade operacional

Comandos úteis:

```bash
python3 traceloc.py -a "Rua X" --cache-clear
python3 traceloc.py -p "+5511999999999" --no-cache
```

---

## 📤 Formatos de Saída

- `--format human` (leitura humana)
- `--format json` (integrações/API)
- `--format csv` (planilhas e BI)

---

## 🎨 Identidade do Projeto

TraceLoc foi projetado com foco em:
- estética técnica de **red team / threat intelligence**
- simplicidade de uso em linha de comando
- documentação clara para uso operacional e educacional

---

## ⚠️ Aviso Legal

Uso destinado a **pesquisa, educação e análise autorizada**.
Você é responsável por cumprir leis locais, políticas de provedores e termos de APIs utilizadas.

---

## 👤 Autor

**Red Team Engineering**

Se quiser, no próximo passo eu também posso criar:
- logo SVG do projeto
- tema terminal para demonstrações
- roadmap visual (milestones)
