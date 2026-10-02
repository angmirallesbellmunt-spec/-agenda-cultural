# Agenda cultural — prototip amb 3 connectors

Flux: **webs d'origen → connectors Python → `data/events.json` normalitzat → `index.html`**.

## Esquema únic
Cada activitat té: `id`, `title`, `image`, `municipality`, `venue`, `category`, `description`, `url`, `source`, `sessions[{date,time}]`.

## Executar
```bash
python -m pip install -r requirements.txt
python update.py
python serve.py
```
Obre `http://localhost:8000`.

`update.py` imprimeix una validació per connector: nombre d'activitats i quantes tenen imatge, sessions, espai i municipi.

## Automatització
S'inclou un workflow de GitHub Actions que executa l'actualització cada dia i desa el JSON actualitzat al repositori.

## Nota important
Els connectors fan scraping de webs de tercers. S'han construït amb selectors redundants i fallbacks, però si una web canvia estructuralment caldrà ajustar el connector corresponent. El Museu de l'Empordà és el connector més defensiu perquè el tema WordPress pot exposar les activitats mitjançant targetes/enllaços diferents.
