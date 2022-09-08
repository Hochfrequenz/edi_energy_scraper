# edi-energy.de scraper

<!--- you need to replace the `organization/repo_name` in the status badge URLs --->

![Unittests status badge](https://github.com/Hochfrequenz/edi_energy_scraper/workflows/Unittests/badge.svg)
![Coverage status badge](https://github.com/Hochfrequenz/edi_energy_scraper/workflows/Coverage/badge.svg)
![Linting status badge](https://github.com/Hochfrequenz/edi_energy_scraper/workflows/Linting/badge.svg)
![Black status badge](https://github.com/Hochfrequenz/edi_energy_scraper/workflows/Black/badge.svg)
![PyPi Status Badge](https://img.shields.io/pypi/v/edi_energy_scraper)

The Python package `edi_energy_scraper` provides easy to use methods to mirror the website edi-energy.de.

### Rationale / Why?

If you'd like to be informed about new regulations or data formats being published on edi-energy.de you can either

- visit the site every day and hope that you see the changes if this is your favourite hobby,
- or automate the task.

This repository helps you with the latter. It allows you to create an up-to-date copy of edi-energy.de on your local
computer. Other than if you mirrored the files using `wget` or `curl`, you'll get a clean and intuitive directory
structure.

From there you can e.g. commit the files into a VCS, scrape the PDF/Word files for later use...

We're all hoping for the day of true digitization on which this repository will become obsolete.

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
from edi_energy_scraper import EdiEnergyScraper

scraper = EdiEnergyScraper(path_to_mirror_directory="edi_energy_de")
scraper.mirror()
```

This creates a directory structure:

```
-|-your_script_cwd.py
 |-edi_energy_de
    |- past (contains archived files)
        |- ahb.pdf
        |- ahb.docx
        |- ...
    |- current (contains files valid as of today)
        |- mig.pdf
        |- mig.docx
        |- ...
    |- future (contains files valid in the future)
        |- allgemeine_festlegungen.pdf
        |- schema.xsd
        |- ...
```

To prevent a DOS, by default the script waits a random time in between 1 and 10 seconds between each file download. You can override this behaviour
by providing your own "slow down" method:

```python
from edi_energy_scraper import EdiEnergyScraper
from time import sleep

scraper = EdiEnergyScraper(path_to_mirror_directory="edi_energy_de",
                           dos_waiter=lambda: sleep(0))  # disable DOS protection
```

## How to use this Repository on Your Machine (for development)

Please follow the instructions in
our [Python Template Repository](https://github.com/Hochfrequenz/python_template_repository#how-to-use-this-repository-on-your-machine)
. And for further information, see the [Tox Repository](https://github.com/tox-dev/tox).

## Contribute

You are very welcome to contribute to this template repository by opening a pull request against the main branch.
