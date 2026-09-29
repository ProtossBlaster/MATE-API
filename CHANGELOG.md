# Changelog

## 0.1.0a14 — 2026-09-30

**Un flag di ricarica letto dall'auto torna all'auto com'era.** Il comando 190 rimanda tutto il
piano, e solo `chargeEnable` e `chargesoc` li sceglie chi chiama: `circulation` e `recharge` si
leggono dal `config.3` dell'auto e si riscrivono tali e quali. Tutti e due venivano controllati
contro {0, 1} — un dominio supposto, mai misurato. La C10 di @jcconca pubblica `circulation=2`,
misurato nel pacchetto diagnostico che ha prodotto proprio la nomina della 0.1.0a13
(`invalid charge flag circulation=2`, leapmotor-mate #343): da allora ogni automazione notturna
sua falliva. Quei due adesso accettano qualunque intero l'auto abbia pubblicato e rifiutano solo un
valore che non si è potuto LEGGERE — `None`, `''`, `'1'`, `1.0`, un booleano — sempre per nome e con
il valore. `chargeEnable` tiene 0/1: è un interruttore, e nessuno lo legge dall'auto per riscriverlo.

## 0.1.0a13 — 2026-09-29

**Un flag di ricarica rifiutato dice quale.** Nel comando 190 viaggiano tre flag —
`chargeEnable`, `circulation`, `recharge` — e qualunque valore di uno qualunque di essi che non
fosse l'intero 0 o 1 produceva la stessa identica frase, `invalid charge flag`. Due dei tre non li
sceglie chi chiama: `circulation` e `recharge` si leggono dall'auto e si riscrivono tali e quali,
quindi un'auto che ne pubblica un altro fermava il proprietario con un messaggio che non ne nomina
nessuno (leapmotor-mate #343, @jcconca: il primo commento ha dovuto chiedere al segnalante di
leggersi quei campi dentro la propria auto).

Adesso il rifiuto nomina il flag e il valore che portava — `invalid charge flag circulation=2` —
e siccome chi chiama registra già il rifiuto, la risposta arriva nel suo log senza una chiamata al
cloud in più. Sono flag: nessun VIN, nessun token, niente da oscurare.

## 0.1.0a12 — 2026-09-28

**Verifica stretta dei certificati**: Python 3.13 accende `VERIFY_X509_STRICT` per default in
`ssl.create_default_context()`, e i certificati di Leapmotor non la passano. Il certificato del
server `appgateway.leapmotor-international.de` porta `basicConstraints CA:FALSE` **insieme** a
`keyCertSign` nel key usage, combinazione che la verifica stretta rifiuta
(`Key usage keyCertSign invalid for non-CA cert`). La stessa contraddizione sta nel certificato
applicativo che il client presenta: è un errore di modello in tutta la loro PKI, e da questa parte
non si può riemettere niente.

Misurato il 28/09/2026 contro il gateway vero, stesso OpenSSL 3.6.3, cambiando solo l'interprete:
Python 3.12.13 completa l'handshake (TLSv1.3), Python 3.14.7 lo rifiuta.

Il contesto di verifica è ora costruito da `transport.tls_context(ca_file)`, che toglie il flag
**esplicitamente** invece di limitarsi a non metterlo. È una deroga stretta: quel contesto si fida
di **un solo** certificato — la sub-CA passata al trasporto — e il trasporto parla solo a una lista
chiusa di host, quindi i controlli stretti stavano sopra un'ancora già pinnata.

## 0.1.0a11 — 2026-09-27

**Rinnovo della sessione**: una sessione si può rinnovare invece di ricomprarla con un login.

Misurato sul cloud vero il 27/09/2026. La risposta di login porta `refreshToken`,
`tokenExpireTime` (**7200 s**) e `refreshTokenExpireTime` (**604799 s**, sette giorni), e
`POST /base/base-user/token/v1/refresh` con `{"refreshToken": …}` risponde `code 0` con una
sessione intera nuova: token d'accesso, token di rinnovo e i parametri di firma. Il certificato
di account **non** viene riemesso, quindi la sessione conserva la coppia che ha già.

### Modifiche

- `LoginClient.refresh(session, device_id=…)`: una sola richiesta, nessun tentativo automatico,
  stessa forma di errore del login. Un rifiuto (`302010219 Token refresh error`) diventa
  `LoginUnavailable`, mai una sessione lasciata zitta com'era. Il fornitore del certificato di
  account non viene mai chiamato.
- `CloudSession` porta `refresh_token` e `refresh_expires_at`, fuori da `repr` come ogni altro
  materiale di sessione, più `renewable(now)`.
- **La durata del token la dichiara il cloud.** Prima ogni sessione era tagliata a mezz'ora:
  era una scelta prudente fatta quando niente diceva altro, ed è la ragione per cui
  un'installazione spendeva un login ogni trenta minuti. Ora il limite è `tokenExpireTime`
  quando c'è; dove il cloud non dichiara niente, restano i trenta minuti di prima.
- Una durata dichiarata che non sia un numero intero positivo entro un mese viene **rifiutata**,
  non indovinata: una sessione non deve sopravvivere al proprio token perché un campo è arrivato
  malformato.

## 0.1.0a10 — 2026-09-27

Migrazione completa ai **comandi V3 per ogni modello**, non più solo per la B10.
Il permesso non lo decide più il nome del modello ma il dato che il cloud pubblica
per quel veicolo — `abilities`, `rightList`, `moduleRights` — e il rifiuto del cloud
stesso: un comando che quell'auto non ha torna con `result: 40` (无此权限) senza che
il veicolo si muova.

### Modifiche

- `permission_decision()` non riceve più il modello: la decisione era già
  indipendente dal modello tranne che nell'eccezione di omissione del proprietario,
  che ora vale su ogni modello. `bindcars` può omettere `rightList`/`moduleRights`
  per l'auto dell'account e l'app ufficiale ne ricava i permessi dalle `abilities`:
  è la stessa app per tutta la gamma. Una lista di permessi esplicitamente vuota
  resta un rifiuto, e un'auto condivisa non ha l'eccezione su nessun modello.
- `prepare()` non rifiuta più i modelli diversi dalla B10. `carType` resta nel
  binding per le scelte di payload del chiamante, non concede né nega un comando.
- `air()` accetta lo spegnimento completo nel corpo intero a sette campi e non
  rimodella più il payload. I due modelli misurati vogliono forme **opposte**: la
  B10/C10 obbedisce a `{"operate":"off"}` nudo e ignora il corpo intero, la T03
  obbedisce a `operate: "off"` solo dentro il corpo intero e ignora la forma nuda
  (verificato in auto rileggendo `acSwitch`, non da un ACK: il cloud risponde
  `code: 0` a tutte le varianti). `close` viene corretto in `off` sul posto,
  conservando la forma scelta dal chiamante. La riscrittura misurata
  `wind` → `nohotcold` si applica solo quando il clima viene acceso.
- Il clima non è più bloccato sull'`ability`: la T03 europea omette AC_ON (codice 6) e
  raffredda comunque — misurato in auto e riportato in tutto l'ecosistema (Mate #67) — quindi
  un cancello sull'`ability` nasconderebbe la funzione più usata di quel modello. Il codice
  resta documentato in `COMMAND_RULES`; il nuovo `ABILITY_NOT_GATED` dice quali codici NON
  valgono come cancello, e si aggiunge solo con una misura. Il diritto dell'account, il modulo
  di controllo e il rifiuto del cloud restano in vigore.
- Sentinella migrata: comando 220 con il contratto del client V1
  (`{"value":"1"|"0"}`, diritto 220). Nessun codice di `ability` è mai stato
  identificato nell'app, quindi valgono il diritto dell'account, il modulo di
  controllo e il rifiuto del cloud. Il comando 400 resta disabilitato: lo
  disabilita il percorso di disponibilità dell'app ufficiale.
- Il limite dei sedili posteriori nella preparazione è dell'adattatore, non di un
  modello: il messaggio non nomina più la B10.

### Cosa resta non provato

L'accettazione del cloud non è esecuzione fisica, su nessun modello. Le prove in
auto restano confermate solo sulla B10.

## 0.1.0a9 — 2026-09-26

- Corretto il ripristino della DACL dei file privati già esistenti su Windows:
  i flag di ereditarietà OICI si applicano alle directory, non ai file.
- Regressione Windows nativa: protezione di un file esistente, verifica delle ACL
  e rimozione di accessi aggiuntivi senza modificare i byte del file.

## 0.1.0a8 — 2026-09-26

- Materiale account su Windows protetto da una DACL verificata, riservata
  all’utente corrente e trasmessa ai nuovi file delle generazioni.
- Validazione di sola lettura della directory privata per disponibilità e
  ritiro esplicito delle generazioni; su POSIX restano obbligatori permessi 0700.
- Test Windows nativi delle ACL e dei permessi ereditati, oltre alla suite Linux.
- Versione del pacchetto indipendente dal protocollo comandi V3.

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
