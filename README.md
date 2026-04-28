## Angivelse af borgers primære organisationer

Automatisering der sammenligner en foruddefineret liste over godkendte organisationer med borgeres tilknyttede organisationer i KMD Nexus. Ved match sættes den pågældende organisation som borgerens primære organisation.

## Hvad gør robotten?

1. **Indlæser godkendte organisationer** fra en foruddefineret liste (`organizations.py`)
2. **Henter alle borgere** tilknyttet hver godkendt organisation via KMD Nexus
3. **Filtrerer** borgere uden CPR-baseret identifikator og testpersoner fra
4. **Opretter arbejdskø** med borgere og deres organisation
5. **Behandler arbejdskøen** – for hvert element hentes borgerens organisationer i Nexus
6. **Sætter primær organisation** hvis borgeren er tilknyttet organisationen og den ikke allerede er primær
7. **Sporer aktivitet** via ODK tracking-klient

## Forudsætninger

- Python ≥ 3.13
- [`uv`](https://docs.astral.sh/uv/) til pakkehåndtering
- Adgang til **Automation Server** (arbejdskø)
- Adgang til **KMD Nexus** (produktion)
- En **Odense SQL Server**-konto til aktivitetssporing

## Installation

```bash
uv sync
```

## Konfiguration

Kopiér `.env.example` til `.env` og udfyld følgende:

| Variabel | Beskrivelse |
|---|---|
| `ATS_URL` | URL til Automation Server |
| `ATS_TOKEN` | API-token til Automation Server _(valgfri ved lokal kørsel)_ |
| `ATS_WORKQUEUE_OVERRIDE` | ID på arbejdskø _(valgfri tilsidesættelse)_ |

Legitimationsoplysninger til KMD Nexus og Odense SQL Server hentes automatisk fra Automation Server Credentials under nøglerne `KMD Nexus - produktion` og `Odense SQL Server`.

## Kørsel

```bash
# Fyld arbejdskøen med borgere fra godkendte organisationer
uv run python main.py --queue

# Behandl arbejdskøen
uv run python main.py
```

### Argumenter

| Argument | Beskrivelse |
|---|---|
| `--queue` | Fyld arbejdskøen og afslut (kør ingen behandling) |

## Afhængigheder

| Pakke | Formål |
|---|---|
| `automation-server-client` | Arbejdskø-håndtering og credential-opslag |
| `kmd-nexus-client` | Integration med KMD Nexus |
| `odk-tools` | Aktivitetssporing |
| `openpyxl` | Læsning af Excel-filer |
| `pandas` | Databehandling |

## Persondatasikkerhed

Robotten behandler personoplysninger på vegne af Odense Kommune, herunder CPR-numre, der udgør direkte identifikation af fysiske personer (jf. GDPR art. 6).

- Ingen personoplysninger må lægges i dette repository — hverken som testdata, i kode eller i kommentarer
- CPR-numre behandles udelukkende i hukommelsen under kørsel og skrives ikke til logfiler eller filer på disk
- Legitimationsoplysninger håndteres udelukkende via miljøvariabler (`.env`) og Automation Server Credentials — aldrig i kildekode
- `.env`-filen er ekskluderet via `.gitignore` og må aldrig committes
- Testpersoner med kendte dummy-CPR-numre filtreres eksplicit fra inden behandling
