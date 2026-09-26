# Changelog

## 0.1.0a7 — 2026-09-26

Aggiornamento del client **MATE-API per Leapmotor**, successivo a `0.1.0a6`.
Il supporto ai **comandi V3** è distinto dalla versione del pacchetto `0.1.0a7`.
Il nome della distribuzione e gli import Python restano `mate-api` e
`leapmotor_cloud`. Nessuna pubblicazione PyPI è implicita.

### Correzioni incluse

- Capacità e diritti dei comandi allineati all'SDK e ai generatori Mate originali.
- Identità dispositivo della sessione ricavata dai metadati del token ricevuto
  tramite TLS autenticato, preservando l'identità dell'installazione per il login.
- Diagnostica login con stage, stato HTTP e codice API limitati e senza segreti.
- Un solo invio per chiamata esplicita di login; nessun retry automatico.
  Coordinamento e intervallo fra tentativi affidati all'integrazione.
- Test sintetici aggiornati e note sullo schema storico cloud verificato.

### Documentazione e confezionamento

- README dedicato a installazione, comandi V3, requisiti e compatibilità.
- Riferimento tecnico precedente conservato in PROTOCOL.md.
- Metadati pacchetto e stato aggiornati a 0.1.0a7; tag v0.1.0a7.
- Test dell'inventario esterno opzionale compatibile anche con checkout vicini
  alla radice del filesystem: assenza del fixture segnalata come skip.

Questa versione non cambia gli endpoint di login V1 o la firma 2.0 e non abilita
nuovi modelli. Certificati, chiavi e parametri applicativi privati non sono inclusi.
La release resta alpha: non è una certificazione di compatibilità fisica completa.

## Serie sorgente 0.1.0a1–0.1.0a6

Sviluppo sperimentale precedente: firma e letture cloud, login indipendente,
protezione PIN, materiale account, recupero sessioni e interfaccia Mate.
Questi numeri descrivono la cronologia del sorgente; non attestano l'esistenza
di corrispondenti tag o release GitHub pubblicati.
