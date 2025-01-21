# edi-energy.de scraper

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Unittests status badge](https://github.com/Hochfrequenz/edi_energy_scraper/workflows/Unittests/badge.svg)
![Coverage status badge](https://github.com/Hochfrequenz/edi_energy_scraper/workflows/Coverage/badge.svg)
![Linting status badge](https://github.com/Hochfrequenz/edi_energy_scraper/workflows/Linting/badge.svg)
![Black status badge](https://github.com/Hochfrequenz/edi_energy_scraper/workflows/Black/badge.svg)
![PyPi Status Badge](https://img.shields.io/pypi/v/edi_energy_scraper)
![Python Versions (officially) supported](https://img.shields.io/pypi/pyversions/edi_energy_scraper.svg)

The Python package `edi_energy_scraper` provides easy to use methods to mirror the free documents on bdew-mako.de.

### Rationale / Why?

If you'd like to be informed about new regulations or data formats being published on bdew-mako.de you can either

- visit the site every day and hope that you see the changes if this is your favourite hobby,
- or automate the task.

This repository helps you with the latter. It allows you to create an up-to-date copy of edi-energy.de on your local
computer. Other than if you mirrored the files using `wget` or `curl`, you'll get a clean and intuitive directory
structure.

From there you can e.g. commit the files into a VCS (like e.g. our [edi_energy_mirror](https://github.com/Hochfrequenz/edi_energy_mirror)), scrape the PDF/Word files for later use...

We're all hoping for the day of true digitization on which this repository will become obsolete.

### See also
There is a similar project in C# by Fabian Wetzel: [fabsenet/edi-energy-extracto](https://github.com/fabsenet/edi-energy-extractor/).
Other than this project, it stores the downloaded data in a database instead of a file system.
It also works with `bdew-mako.de`.

## How to use the Package (as a user)

Install via pip:

```bash
pip install edi_energy_scraper
```

Create a directory in which you'd like to save the mirrored data:

```bash
mkdir edi_energy_de
```

Then import it and start the download:

```python
import asyncio
from edi_energy_scraper import EdiEnergyScraper


# add the following lines to enable debug logging to stdout (CLI)
# import logging
# import sys
# logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

async def mirror():
    scraper = EdiEnergyScraper(path_to_mirror_directory="edi_energy_de")
    await scraper.mirror()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.run(mirror())

```

This creates a directory structure:

```
-|-your_script_cwd.py
 |-edi_energy_de
    |- FV2310 (contains files valid since 2023-10-01)
        |- ahb.pdf
        |- ahb.docx
        |- ...
    |- FV2404 (contains files valid since 2024-04-03)
        |- mig.pdf
        |- mig.docx
        |- ...
    |- FV2504 (contains files valid since 2025-06-06)
        |- allgemeine_festlegungen.pdf
        |- schema.xsd
        |- ...
```

> [!TIP]
> You can extract the information encoded into the filenames:
> ```python
> from edi_energy_scraper import DocumentMetadata
> structured_information = DocumentMetadata.from_filename("AHB_COMDIS_1.0f_99991231_20250605_20250605_8872.pdf")
> # DocumentMetadata(kind='MIG', edifact_format=<EdifactFormat.REQOTE: 'REQOTE'>, valid_from=datetime.date(2023, 9, 30), valid_unt...traordinary_publication=True, is_error_correction=False, is_informational_reading_version=True, additional_text=None, id=10071)
```

## How to use this Repository on Your Machine (for development)

Please follow the instructions in
our [Python Template Repository](https://github.com/Hochfrequenz/python_template_repository#how-to-use-this-repository-on-your-machine)
. And for further information, see the [Tox Repository](https://github.com/tox-dev/tox).

## Contribute

You are very welcome to contribute to this template repository by opening a pull request against the main branch.
