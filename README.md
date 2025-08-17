🎤 Audio-Stream (Meeting, Aufnahme)
          │
          ▼
  [Chunker / Splitter]
  - schneidet Audio in 30–60s Blöcke
  - optional mit 5s Überlappung
          │
          ▼
  [Whisper Worker(s)]
  - Transkription pro Block (parallel möglich)
  - Ausgabe: Text + Timestamps
          │
          ▼
  [Message Queue] (z. B. Redis, Kafka, Celery)
  - speichert die fertigen Transkript-Blöcke
          │
          ▼
  [Vektor-Datenbank] (z. B. Chroma, Weaviate, pgvector)
  - jeder Block = Dokument mit Zeitstempel
          │
          ├──► (1) 🔍 Suche im Meeting (Q&A währenddessen möglich)
          │
          └──► (2) 📝 Summarizer Worker
                 - holt die letzten X Blöcke (z. B. 1 Minute)
                 - fasst sie mit LLM zusammen
                 - am Ende: globale Meeting-Zusammenfassung
