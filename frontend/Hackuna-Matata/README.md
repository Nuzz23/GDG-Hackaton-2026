src/
├── assets/         #file statici e.g. immagini, icone, font e loghi.
├── components/     # componenti UI dumb e riutilizzabili (e.g. Button.tsx, Modal.tsx, Input.tsx).
├── hooks/          # custom hooks React condivisi in tutta l'app (es. useDebounce.ts, useAuth.ts).
├── pages/          # componenti che fungono da pagina intera, collegati al router (es. Home.tsx).
├── routes/         # configurazione delle rotte (e.g. con react-router-dom).
├── services/       # file per le chiamate API o integrazioni di terze parti (e.g. apiClients.ts).
├── styles/         # stili globali o file CSS.
├── types/          # definizioni TypeScript globali, interfacce e tipi (e.g. user.types.ts).
├── utils/          # funzioni helper pure e formattatori (e.g. formatDate.ts, validators.ts).
├── App.tsx         # punto di ingresso della UI e configurazione dei provider principali.
└── main.tsx        # punto di montaggio dell'applicazione React sul DOM.