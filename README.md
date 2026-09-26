# MATE-API — client cloud per Leapmotor

Client Python indipendente e non ufficiale per le **API cloud di Leapmotor**, con supporto ai **comandi V3**,
sviluppato per la migrazione di Mate dal precedente SDK `leapmotor_api`.

**Versione: `0.1.0a9` · Stato: alpha · Python: 3.11–3.14**

Il nome del pacchetto rimane `mate-api`; gli import restano `leapmotor_cloud`.
Questa è una libreria per sviluppatori: non include l'applicazione Mate, la sua
interfaccia web o un'installazione Docker completa.

## Cosa significa V3

| Elemento | Versione / nome |
| --- | --- |
| Pacchetto Python | `mate-api==0.1.0a9` |
| Tag GitHub | `v0.1.0a9` |
| Comandi cloud | `/app/app-control-service/v3/api/appremotectl` |
| Configurazione e appuntamenti | endpoint `/carownerservice/v3/...` |
| Login | `/base/base-user/account/v1/login` |
| Firma delle richieste | `x-api-signature-version: 2.0` |

**V3 indica la versione dei comandi cloud.** La versione della libreria segue
una numerazione separata: `0.1.0a9` prosegue `0.1.0a8`. Gli endpoint mantengono
le rispettive versioni: login V1 e firma 2.0 rimangono necessari.

## Funzionalità disponibili

- Login indipendente, sessioni autenticate, firma richieste e trasporto TLS verificato.
- Lettura veicoli, telemetria, configurazione e storico cloud con paginazione.
- Contratti dei comandi B10 con controllo di capacità, permessi e parametri.
- Protezione del PIN e gestione locale del materiale del certificato account.
- Interfaccia di compatibilità per integrare il nuovo client in Mate.
- Metadati diagnostici limitati per gli errori di login, senza esporre risposte private.

Le ultime correzioni allineano i codici delle capacità ai comandi generati dal Mate
originale e usano l'identità del dispositivo associata alla sessione restituita dal
server. L'identità dell'installazione rimane quella usata per il login.

## Installazione della versione

Da GitHub, senza dipendere dalla presenza del pacchetto su PyPI:

```sh
python -m pip install "mate-api[certificates] @ git+https://github.com/ProtossBlaster/MATE-API.git@v0.1.0a9"
```

Per sviluppo e verifica locale:

```sh
git clone https://github.com/ProtossBlaster/MATE-API.git
cd MATE-API
git checkout v0.1.0a9
python -m pip install '.[certificates]'
python -m unittest discover -s tests -v
python -c "from importlib.metadata import version; print(version('mate-api'))"
```

L'extra `certificates` installa `cryptography`. I test sono offline e non inviano
comandi a un'auto. Un test può essere saltato se manca l'inventario esterno opzionale.

## Cosa serve per collegarsi

L'integrazione deve fornire credenziali dell'account, identità dell'installazione,
certificato e chiave applicativi validi, parametri privati necessari e gestione del
certificato account. **Questo repository non distribuisce quel materiale.**
Non basta installare il pacchetto per ottenere un accesso cloud funzionante.

`LoginClient` riceve esplicitamente trasporto, materiale applicativo, orologio,
generatore nonce e provider del certificato account. Il coordinamento dei processi,
il database e l'interfaccia utente appartengono all'integrazione Mate separata.
Il nome storico `api_v2_bridge` di quell'adapter non cambia gli endpoint V3 usati.

## Compatibilità e verifiche

**B10 è l'unico modello abilitato per i comandi nel percorso migrato.** Non tutti
i comandi e gli allestimenti sono stati provati fisicamente. Non vengono abilitati
altri modelli sulla sola base dei test sintetici.

La qualifica precedente a questa release comprende 190 test canonici (uno skip
opzionale), CI su Python 3.11–3.14 e confronto di 32 casi di generazione comandi
con Mate originale. Login e letture reali sono riusciti nel laboratorio 4004.
Una chiusura autorizzata è stata accettata dal cloud; la telemetria successiva era
recente e indicava chiuso. Questo non dimostra una transizione fisica delle serrature.

Un esito cloud positivo non conferma l'esecuzione fisica. I comandi con esito ambiguo
non devono essere ritentati automaticamente. Restano da qualificare revoca reale,
recupero, sonno del veicolo, altri modelli e provisioning pubblico automatico.

## Documentazione e versioni

- [Changelog](CHANGELOG.md): modifiche e versionamento.
- [Protocollo e integrazione](PROTOCOL.md): contratti, login, PIN e certificati.
- [Risultati della migrazione](MIGRATION_NOTES.md): schema storico e mapping verificati.
- [Migrazione e rollback](MIGRATION.md): confini dell'integrazione.
- [Stato e requisiti di rilascio](STATUS.md): copertura e limiti residui.
- [Sicurezza](SECURITY.md): segnalazioni e gestione dei dati privati.
- [Release GitHub](https://github.com/ProtossBlaster/MATE-API/releases).

Codice con licenza MIT. Progetto non ufficiale, non affiliato a Leapmotor.
La licenza del codice non concede diritti sui certificati, sulle chiavi o sugli
asset dell'applicazione Leapmotor.
