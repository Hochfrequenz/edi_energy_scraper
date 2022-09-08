"""
A minimal working example on how to use this package
"""
from edi_energy_scraper import EdiEnergyScraper

scraper = EdiEnergyScraper(path_to_mirror_directory="edi_energy_de")
scraper.mirror()
