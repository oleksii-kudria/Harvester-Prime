# Harvester Prime

Utilities for processing DHCP log files.

## Functionality

* Collect DHCP log entries from CSV files in a directory.
* Normalize records into a consistent structure.
* Track the first and last times each MAC address appears in the logs.
* Write results to an interim CSV file while skipping duplicate rows.

## Input

Raw DHCP log CSV files. Locations are configurable via `configs/base.yaml` (default: `data/raw/dhcp`).

## Output

A normalized CSV file containing unique DHCP records (default: `data/interim/dhcp.csv`).
Each record includes the earliest (`firstDate`) and latest (`lastDate`) timestamps for
when the MAC address was seen.

## Usage

Ensure dependencies are installed and run:

```bash
python scripts/process.py
```

The script reads configuration, processes the raw logs and stores the normalized output.

See `src/app/collectors/files.py` for implementation details.

## Configuration

Directory and file locations used by the scripts can be adjusted in
`configs/base.yaml`. The following keys are available:

- `raw_dhcp`: directory containing raw DHCP logs.
- `interim_dhcp`: path to the normalized interim CSV file.
- `raw_validation`: directory with validation CSV files.
- `validation_report`: report produced from the validation step.
- `raw_arm`: directory with ARM inventory CSV files.
- `raw_mkp`: directory with MKP inventory CSV files.
- `arm_mkp_report`: report produced from ARM and MKP checks.

An optional `configs/local.yml` can define additional behaviour. To skip
specific MAC addresses during processing add them under the
`ignore.mac` section:

```yaml
ignore:
  mac:
    phone: "B6:87:29:FC:51:D2"
    laptop: "56:97:0E:87:72:41"
```

MAC addresses listed there are excluded from the generated
`data/interim/dhcp.csv` file.

## Raw data directories

The script reads several directories under `data/raw`. Each CSV file must
contain the listed columns. Columns are read as text unless noted otherwise.

| Directory | Required columns | Data type / values |
|-----------|-----------------|-------------------|
| `data/raw/dhcp/*.csv` | `logSourceIdentifier`, `sourcMACAddress`, `payloadAsUTF`, `deviceTime` | MAC in `sourcMACAddress` must be `XX:XX:XX:XX:XX:XX` or `XX-XX-XX-XX-XX-XX`. `deviceTime` is a Unix timestamp in milliseconds. IP and host name are parsed from `payloadAsUTF`. |
| `data/raw/ubiq/*.csv` | `source`, `name`, `mac`, `ip`, `date` | `mac` uses the same MAC format as above. `ip` is an IPv4 address. `date` is in `%b %d %Y %I:%M %p` (e.g. `Sep 19 2024 07:24 PM`). |
| `data/raw/validation/*.csv` | `ip`, `mac` | `ip` is IPv4, `mac` uses standard MAC format. |
| `data/raw/arm/*.csv` | `MAC`, `Hostname`, `Власник`, `Тип ПК`, `IP` | `MAC` is a physical MAC address, `IP` is IPv4. Other columns are free text describing the workstation. |
| `data/raw/mkp/*.csv` | `Статичний MAC`, `Модель`, `Відповідальний`, `Тип МКП`, `Динамічний MAC` | `Статичний MAC` and `Динамічний MAC` are MAC addresses. The rest are free text. |
| `data/raw/other/*.csv` | `type`, `name`, `mac` | `mac` must be a valid MAC address. `type` describes the device class (e.g. printer). |

## Processing steps

`scripts/process.py` performs the following operations in sequence:

1. **Normalize DHCP logs** – read `data/raw/dhcp` and write unique records
   to `data/interim/dhcp.csv`.
2. **Append Ubiq data** – convert Ubiq CSVs and add them to the interim DHCP
   file.
3. **Validation check** – compare MACs from `data/raw/validation` with the
   DHCP list and write a report to `data/result/report1.csv`.
4. **ARM interim** – match ARM inventory MACs with DHCP data and append
   matches to `data/interim/verified.csv` with `type="arm"`.
5. **MKP interim** – match MKP inventory MACs with DHCP data and append
   matches to the same verified file with `type="mkp"` and optional
   `randmac`.
6. **Other devices** – append entries from `data/raw/other` to
   `data/interim/verified.csv` when their MAC is present in DHCP data.
7. **ARM & MKP reports** – create `data/result/120report2.csv` comparing ARM
   and MKP inventories against DHCP data; new rows include `name`, `ipmac`,
   `owner` and `note`.
8. **Pending devices** – write DHCP records absent from the verified list to
   `data/interim/pending.csv` with a device `type` inferred from the host
   name.

## Result files

The processing steps produce these CSV files:

- `data/interim/dhcp.csv` – columns: `source`, `ip`, `mac`, `name`,
  `firstDate`, `lastDate`.
- `data/interim/verified.csv` – columns: `type`, `source`, `name`, `ip`,
  `mac`, `randmac`, `owner`, `note`, `firstDate`, `lastDate`.
- `data/interim/pending.csv` – columns: `type`, `source`, `ip`, `mac`,
  `name`, `firstDate`, `lastDate`.
- `data/result/report1.csv` – columns: `name`, `ipmac`, `note`.
- `data/result/120report2.csv` – columns: `name`, `ipmac`, `owner`, `note`.
