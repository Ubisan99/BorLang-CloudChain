# BoRLang v3.1 — External Bindings Manual

## Introduzione

BoRLang v3.1 include 25+ binding nativi alle librerie Python più importanti:
**Pandas, PyTorch, Hugging Face, LangChain, Plotly, spaCy, NLTK, Requests, Chroma, Pydantic**.

Ogni binding è una funzione BoRLang che incapsula la logica Python.
Niente boilerplate — call dirette alle API sottostanti.

**Prerequisito**: `pip install -r requirements.txt` per far disponibili tutte le librerie.

---

## 1. DATA MANIPULATION (Pandas/Polars)

### `df_read_csv(path: str) → Dict`

Legge CSV e ritorna dict con structure tabulare.

```borlang
data = df_read_csv("sales.csv")
print(data.rows)          # list di dict, uno per riga
print(data.columns)       # list di nomi colonne
print(data.shape)         # [num_rows, num_cols]
print(data.dtypes)        # {col: type_string}
```

**Ritorna:**
```
{
  "rows": [{col: val, ...}, ...],
  "shape": [100, 5],
  "columns": ["id", "name", "amount", ...],
  "dtypes": {"amount": "int64", "name": "object", ...}
}
```

---

### `df_to_csv(rows: List[Dict], path: str) → bool`

Scrive list di dict a CSV.

```borlang
data = [
    {id: 1, name: "Alice", amount: 100},
    {id: 2, name: "Bob", amount: 200}
]
df_to_csv(data, "output.csv")  # true se ok
```

---

### `df_filter(rows: List[Dict], column: str, operator: str, value: Any) → List[Dict]`

Filtra righe per colonna + condizione.

```borlang
all_sales = df_read_csv("sales.csv").rows

# Filtra: amount >= 500
high_value = df_filter(all_sales, "amount", ">=", 500)

# Filtra: name contains "Alice"
alice_sales = df_filter(all_sales, "name", "contains", "Alice")

# Filtra: status == "completed"
completed = df_filter(all_sales, "status", "==", "completed")
```

**Operatori supportati:** `==`, `!=`, `<`, `>`, `<=`, `>=`, `contains`

---

### `df_sort(rows: List[Dict], by: str, desc: bool = false) → List[Dict]`

Ordina righe per colonna.

```borlang
# Ascendente
sorted_by_name = df_sort(all_sales, "name", false)

# Discendente
sorted_by_amount = df_sort(all_sales, "amount", true)
```

---

### `df_groupby(rows: List[Dict], by: str, agg: str = "count") → Dict`

Raggruppa e aggrega.

**Aggregazioni:** `count`, `sum`, `mean`, `max`, `min`

```borlang
sales = df_read_csv("sales.csv").rows

# Count per categoria
counts = df_groupby(sales, "category", "count").result
# {"electronics": 42, "clothing": 38, ...}

# Sum per regione
totals = df_groupby(sales, "region", "sum").result
# {"north": 50000, "south": 45000, ...}

# Media per venditore
avgs = df_groupby(sales, "seller", "mean").result
```

---

### `df_head(rows: List[Dict], n: int = 5) → List[Dict]`
### `df_tail(rows: List[Dict], n: int = 5) → List[Dict]`

Prime/ultime N righe.

```borlang
first_10 = df_head(data, 10)
last_5 = df_tail(data, 5)
```

---

## 2. DATA VISUALIZATION (Plotly)

### `plot_line(x: List, y: List, title: str = "", filename: str = null) → str`

Crea line chart.

```borlang
months = ["Jan", "Feb", "Mar", "Apr", "May"]
sales = [1000, 1500, 1200, 1800, 2100]

html = plot_line(months, sales, "Monthly Sales")
# Ritorna HTML. Se filename, salva a disco.

plot_line(months, sales, "Q1 Trend", "chart.html")
# Salva chart.html, ritorna "saved to chart.html"
```

---

### `plot_scatter(x: List, y: List, title: str = "", filename: str = null) → str`

Scatter plot.

```borlang
ages = [25, 30, 35, 40, 45]
salaries = [30000, 45000, 50000, 60000, 75000]

plot_scatter(ages, salaries, "Age vs Salary", "scatter.html")
```

---

### `plot_bar(labels: List[str], values: List, title: str = "", filename: str = null) → str`

Bar chart.

```borlang
categories = ["Q1", "Q2", "Q3", "Q4"]
revenue = [100000, 120000, 115000, 150000]

plot_bar(categories, revenue, "Quarterly Revenue", "bars.html")
```

---

## 3. DEEP LEARNING & GenAI (Hugging Face Transformers)

### `hf_classify(text: str, model: str = "distilbert-base-uncased-finetuned-sst-2-english") → Dict`

Classificazione testo (sentiment, etc).

```borlang
result = hf_classify("I absolutely loved this movie!")
# {label: "POSITIVE", score: 0.9997}

result = hf_classify("This is the worst experience ever.", "distilbert-...")
# {label: "NEGATIVE", score: 0.9995}
```

**Default model:** Sentiment English. Sostituisci per altri task (intent, emotions, etc).

---

### `hf_ner(text: str, model: str = "dslim/bert-base-multilingual-cased-ner") → List[Dict]`

Named Entity Recognition (persone, luoghi, organizzazioni).

```borlang
entities = hf_ner("John Smith works at Google in San Francisco")
# [
#   {text: "John Smith", label: "PER"},
#   {text: "Google", label: "ORG"},
#   {text: "San Francisco", label: "LOC"}
# ]
```

---

### `hf_summarize(text: str, model: str = "facebook/bart-large-cnn") → str`

Riassunto automatico.

```borlang
long_article = "Lorem ipsum dolor sit amet... [1000 parole]"
summary = hf_summarize(long_article)
print(summary)  # Riassunto in 50-150 parole
```

---

### `hf_translate(text: str, src: str = "en", tgt: str = "fr") → str`

Traduzione.

```borlang
italian_text = hf_translate("Hello world", "en", "it")
# "Ciao mondo"

spanish = hf_translate("Good morning", "en", "es")
# "Buenos días"
```

**Lingue supportate:** `en`, `it`, `es`, `fr`, `de`, `pt`, `nl`, ecc.

---

### `hf_embed(texts: List[str], model: str = "sentence-transformers/all-MiniLM-L6-v2") → List[List[float]]`

Sentence embeddings (vettori semantici).

```borlang
sentences = [
    "The cat sat on the mat",
    "A feline rested on the rug",
    "The dog barked loudly"
]

embeddings = hf_embed(sentences)
# [
#   [0.123, 0.456, ...],  # 384 dimensioni
#   [0.124, 0.455, ...],  # simile alla prima
#   [0.201, 0.512, ...]   # diversa
# ]

# Usa con vector store per semantic search
```

---

## 4. LLM ORCHESTRATION (LiteLLM)

### `llm_chat(message: str, model: str = "ollama:qwen2.5:14b", system: str = null) → str`

Chat con LLM locale o remoto.

```borlang
# Con Ollama locale
answer = llm_chat("Qual è la capitale d'Italia?", "ollama:qwen2.5:14b")
print(answer)  # "La capitale dell'Italia è Roma."

# Con system prompt
creative = llm_chat(
    "Scrivi una filastrocca su un gatto",
    "ollama:qwen2.5:14b",
    "Sei un poeta italiano esperto di strofe"
)

# Con API remota (via LiteLLM)
response = llm_chat("Hello", "openai/gpt-4")  # richiede OPENAI_API_KEY
```

---

### `llm_batch_classify(texts: List[str], labels: List[str], model: str = "ollama:qwen2.5:7b") → List[str]`

Classifica multipli testi.

```borlang
reviews = [
    "Prodotto ottimo, molto soddisfatto!",
    "Pessimo, non funziona nulla",
    "Buono ma potrebbe essere più veloce"
]

categories = ["positive", "negative", "neutral"]

results = llm_batch_classify(reviews, categories, "ollama:qwen2.5:7b")
# ["positive", "negative", "neutral"]
```

---

### `llm_extract(text: str, schema: Dict, model: str = "ollama:qwen2.5:14b") → Dict`

Estrai dati strutturati da testo non strutturato.

```borlang
invoice_text = """
Fattura #12345
Cliente: Mario Rossi
Data: 2024-04-27
Importo: €1500
"""

schema = {
    invoice_id: "string",
    customer_name: "string",
    amount: "float"
}

extracted = llm_extract(invoice_text, schema, "ollama:qwen2.5:14b")
# {
#   invoice_id: "12345",
#   customer_name: "Mario Rossi",
#   amount: 1500.0
# }
```

---

## 5. VECTOR DATABASES (Chroma)

### `vec_db_create_chroma(name: str = "default") → Dict`

Crea collection vettoriale in-memory.

```borlang
col = vec_db_create_chroma("documents")
# {collection: <...>, type: "chroma", name: "documents"}
```

---

### `vec_db_add(collection, texts: List[str], ids: List[str] = null, metadatas: List[Dict] = null) → bool`

Aggiungi documenti.

```borlang
docs = [
    "BoRLang è un linguaggio per ML",
    "Ollama gira modelli locali",
    "Vector search è semantico"
]

vec_db_add(col, docs)  # Auto-genera IDs

# Con IDs e metadati personalizzati
vec_db_add(col, docs, ["doc1", "doc2", "doc3"], 
           [{source: "wiki"}, {source: "blog"}, {source: "paper"}])
```

---

### `vec_db_query(collection, query_text: str, k: int = 5) → List[Dict]`

Cerca semanticamente.

```borlang
hits = vec_db_query(col, "Come faccio machine learning?", 5)
# [
#   {id: "doc1", document: "BoRLang è un linguaggio per ML", distance: 0.15},
#   {id: "doc3", document: "Vector search è semantico", distance: 0.42},
#   ...
# ]
```

---

## 6. NLP (spaCy, NLTK)

### `nlp_tokenize(text: str) → List[str]`

Split in token (parole).

```borlang
tokens = nlp_tokenize("Hello, how are you?")
# ["Hello", ",", "how", "are", "you", "?"]
```

---

### `nlp_pos_tag(text: str) → List[tuple]`

Part-of-speech tagging.

```borlang
tags = nlp_pos_tag("The cat is sleeping")
# [("The", "DT"), ("cat", "NN"), ("is", "VBZ"), ("sleeping", "VBG")]
# DT=determiner, NN=noun, VBZ=verb, VBG=verb-gerund
```

---

### `nlp_ner_spacy(text: str, model: str = "en_core_web_sm") → List[Dict]`

Estrai entità con spaCy (persone, luoghi, org).

```borlang
entities = nlp_ner_spacy("Steve Jobs founded Apple in 1976")
# [
#   {text: "Steve Jobs", label: "PERSON"},
#   {text: "Apple", label: "ORG"},
#   {text: "1976", label: "DATE"}
# ]
```

---

### `nlp_sentiment(text: str) → Dict`

Sentiment analysis (TextBlob).

```borlang
result = nlp_sentiment("I love this product!")
# {polarity: 0.85, subjectivity: 0.6}
# polarity: -1.0 (negativo) a 1.0 (positivo)
# subjectivity: 0.0 (oggettivo) a 1.0 (soggettivo)
```

---

## 7. WEB SCRAPING (Requests, BeautifulSoup)

### `scrape_html(url: str) → str`

Fetch HTML da URL.

```borlang
html = scrape_html("https://example.com")
# Ritorna HTML completo della pagina
```

---

### `scrape_parse_html(html: str, selector: str) → List[str]`

Parse HTML con CSS selector.

```borlang
html = scrape_html("https://example.com")

titles = scrape_parse_html(html, "h1")
# Tutte le intestazioni h1

links = scrape_parse_html(html, "a")
# Tutti i link

price_tags = scrape_parse_html(html, ".product .price")
# Tutti gli elementi con classe "price" dentro classe "product"
```

---

### `scrape_json(url: str) → Dict`

Fetch JSON API.

```borlang
data = scrape_json("https://api.example.com/users")
# Ritorna dict parsato da JSON
```

---

## 8. DATA VALIDATION (Pydantic)

### `validate_schema(data: Dict, schema: Dict) → bool`

Valida dict contro schema di tipo.

```borlang
schema = {
    name: "string",
    age: "integer",
    active: "bool",
    score: "float"
}

good = {name: "Alice", age: 30, active: true, score: 9.5}
validate_schema(good, schema)  # true

bad = {name: "Bob", age: "thirty"}  # age non è int
validate_schema(bad, schema)  # false
```

**Tipi supportati:** `string`, `integer`, `float`, `bool`

---

## PATTERN: RAG (Retrieval Augmented Generation)

Combina semantic search + LLM per rispondere a domande su documenti.

```borlang
# 1. Indicizza documenti
col = vec_db_create_chroma("knowledge_base")
docs = [
    "BoRLang supporta ML, vector DB, e agent agentic",
    "Ollama gira modelli open-source locali",
    "LangChain orchestra agenti complessi"
]
vec_db_add(col, docs)

# 2. User fa domanda
question = "Come faccio semantic search?"

# 3. Retrieval — cerca documenti rilevanti
hits = vec_db_query(col, question, 3)
context = ""
for h in hits
    context = context + h["document"] + "\n"
end

# 4. Augmentation — passa contesto a LLM
answer = llm_chat(
    "Context: " + context + "\n\nQ: " + question,
    "ollama:qwen2.5:14b"
)

print(answer)
```

---

## PATTERN: Multi-step Classification

Classifica testo attraverso multipli modelli per robustezza.

```borlang
text = "This movie was absolutely terrible!"

# Step 1: Sentiment HF
hf_result = hf_classify(text)

# Step 2: Sentiment TextBlob
tb_result = nlp_sentiment(text)

# Step 3: Vote
if hf_result.score > 0.8 and tb_result.polarity < 0
    print("NEGATIVE (consensus)")
end
```

---

## PATTERN: Data Pipeline

Leggi → Filtra → Aggrega → Visualizza.

```borlang
# Leggi
data = df_read_csv("sales.csv").rows

# Filtra
high_value = df_filter(data, "amount", ">", 1000)

# Aggrega
by_region = df_groupby(high_value, "region", "sum").result

# Visualizza
labels = keys(by_region)
values = values(by_region)
plot_bar(labels, values, "High-Value Sales by Region", "chart.html")

print("Chart saved to chart.html")
```

---

## TROUBLESHOOTING

**"ModuleNotFoundError: No module named X"**
→ `pip install -r requirements.txt` per installare tutte le dipendenze

**hf_classify/hf_embed ritorna error**
→ Primo uso: scarica il modello (lento, ~500 MB). Attendi. Dopo è cached.

**vec_db_query ritorna [] vuoto**
→ Assicurati di aver aggiunto documenti con `vec_db_add` prima di cercare

**llm_chat non risponde**
→ Ollama deve essere running: `ollama serve`
→ Verifica il modello: `ollama list`

---

## COMPLETENESS

Tutte le 25+ funzioni sono integr ate nativamente in BoRLang v3.1.
Nessun boilerplate — call diretto come funzione BoRLang.

Vedi `borlang_bindings.py` per implementazione Python.
