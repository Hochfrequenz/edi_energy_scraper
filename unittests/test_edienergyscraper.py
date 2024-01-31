from pathlib import Path
from typing import Optional

import pytest
from aioresponses import aioresponses
from bs4 import BeautifulSoup
from maus.edifact import EdifactFormat, EdifactFormatVersion

from edi_energy_scraper import EdiEnergyScraper, Epoch


class TestEdiEnergyScraper:
    """
    A class to test the EdiEnergyScraper.
    """

    @pytest.mark.parametrize(
        "epoch,str_epoch",
        [
            pytest.param(Epoch.CURRENT, "current"),
            pytest.param(Epoch.FUTURE, "future"),
            pytest.param(Epoch.PAST, "past"),
        ],
    )
    def test_epoch_stringify(self, epoch: Epoch, str_epoch: str):
        actual = str(epoch)
        assert actual == str_epoch

    def test_instantiation(self):
        """
        Tests, that the constructor works.
        """
        instance = EdiEnergyScraper(root_url="https://my_url.de/")
        assert not instance._root_url.endswith("/")

    @pytest.mark.datafiles(
        "./unittests/testfiles/index_20210208.html",
    )
    async def test_index_retrieval(self, datafiles):
        """
        Tests that the landing page is downloaded correctly
        """
        with open(datafiles / "index_20210208.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        assert "<!--" in response_body  # original response contains comments, will be removed
        with aioresponses() as mock:
            mock.get("https://www.my_root_url.test", body=response_body)
            ees = EdiEnergyScraper("https://www.my_root_url.test")
            actual_soup = await ees.get_index()
        actual_html = actual_soup.prettify()
        assert "<!--" not in actual_html, "comments should be ignored/removed"
        assert "Startseite: BDEW Forum Datenformate" in actual_html, "content should be returned"

    async def test_get_soup(self, mocker):
        """
        Some links on edi-energy.de are relative. The call of _get_soup should automatically resolve the absolute
        URL of a page if only the relative URL is given.
        """
        ees = EdiEnergyScraper(root_url="https://my_favourite_website.inv/")
        self.has_been_called_correctly = False  # this is not the nicest test setup but hey. it's late.

        async def _request_get_sideffect(*args, **kwargs):
            assert args[0] == "https://my_favourite_website.inv/some_relative_path"
            self.has_been_called_correctly = True

        ees.requests.get = _request_get_sideffect
        try:
            await ees._get_soup(url="/some_relative_path")
        except AttributeError:
            pass
        assert self.has_been_called_correctly  # that's all we care for in this test.

    @pytest.mark.datafiles(
        "./unittests/testfiles/index_20210208.html",
    )
    async def test_dokumente_link(self, datafiles):
        """
        Tests that the "Dokumente" link is extracted from the downloaded landing page.
        """
        with open(datafiles / "index_20210208.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        with aioresponses() as mock:
            mock.get("https://www.edi-energy.de", body=response_body)
            ees = EdiEnergyScraper("https://www.edi-energy.de")
            actual_link = ees.get_documents_page_link(await ees.get_index())
        assert actual_link == "https://www.edi-energy.de/index.php?id=38"

    @pytest.mark.datafiles(
        "./unittests/testfiles/dokumente_20210208.html",
    )
    def test_epoch_links_extraction(self, datafiles):
        """
        Tests that the links to past/current/future documents overview pages are extracted.
        """
        with open(datafiles / "dokumente_20210208.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        soup = BeautifulSoup(response_body, "html.parser")
        actual = EdiEnergyScraper.get_epoch_links(soup)
        assert len(actual.keys()) == 3
        assert (
            actual[Epoch.CURRENT]
            == "https://www.edi-energy.de/index.php?id=38&tx_bdew_bdew%5Bview%5D=now&tx_bdew_bdew%5Baction%5D=list&tx_bdew_bdew%5Bcontroller%5D=Dokument&cHash=5d1142e54d8f3a1913af8e4cc56c71b2"
        )
        assert (
            actual[Epoch.PAST]
            == "https://www.edi-energy.de/index.php?id=38&tx_bdew_bdew%5Bview%5D=archive&tx_bdew_bdew%5Baction%5D=list&tx_bdew_bdew%5Bcontroller%5D=Dokument&cHash=6dd9d237ef46f6eebe2f4ef385528382"
        )
        assert (
            actual[Epoch.FUTURE]
            == "https://www.edi-energy.de/index.php?id=38&tx_bdew_bdew%5Bview%5D=future&tx_bdew_bdew%5Baction%5D=list&tx_bdew_bdew%5Bcontroller%5D=Dokument&cHash=325de212fe24061e83e018a2223e6185"
        )

    @pytest.mark.datafiles(
        "./unittests/testfiles/future_20210210.html",
    )
    def test_epoch_file_map_future_20210210(self, datafiles):
        with open(datafiles / "future_20210210.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        soup = BeautifulSoup(response_body, "html.parser")
        actual = EdiEnergyScraper.get_epoch_file_map(soup)
        assert len(actual.keys()) == 76
        for file_basename in actual.keys():
            # all the future names should contain 99991231 as "valid to" date
            assert "_99991231_" in file_basename
        assert (
            actual["UTILMDAHBWiM3.1bKonsolidierteLesefassungmitFehlerkorrekturenStand18.12.2020_99991231_20210401"]
            == "https://www.edi-energy.de/index.php?id=38&tx_bdew_bdew%5Buid%5D=1000&tx_bdew_bdew%5Baction%5D=download&tx_bdew_bdew%5Bcontroller%5D=Dokument&cHash=dbf7d932028aa2059c96b25a684d02ed"
        )

    @pytest.mark.datafiles(
        "./unittests/testfiles/current_20210210.html",
    )
    def test_epoch_file_map_current_20210210(self, datafiles):
        with open(datafiles / "current_20210210.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        soup = BeautifulSoup(response_body, "html.parser")
        actual = EdiEnergyScraper.get_epoch_file_map(soup)
        assert len(actual.keys()) == 81
        for file_basename in actual.keys():
            # all the current documents are either "open" or valid until April 2021
            assert "_99991231_" in file_basename or "_20210331_" in file_basename
        assert (
            actual["QUOTESMIG1.1aKonsolidierteLesefassungmitFehlerkorrekturenStand15.07.2019_20210331_20191201"]
            == "https://www.edi-energy.de/index.php?id=38&tx_bdew_bdew%5Buid%5D=738&tx_bdew_bdew%5Baction%5D=download&tx_bdew_bdew%5Bcontroller%5D=Dokument&cHash=f01ed973e9947ccf6b91181c93cd2a28"
        )

    @pytest.mark.datafiles(
        "./unittests/testfiles/past_20210210.html",
    )
    def test_epoch_file_map_past_20210210(self, datafiles):
        with open(datafiles / "past_20210210.html", "r", encoding="utf8") as infile:
            response_body = infile.read()
        soup = BeautifulSoup(response_body, "html.parser")
        actual = EdiEnergyScraper.get_epoch_file_map(soup)
        assert len(actual.keys()) == 705

    @pytest.mark.parametrize(
        "file_name, expected_file_name",
        [
            pytest.param(
                "example_ahb.pdf",
                "my_favourite_ahb.pdf",
                id="pdf",
            ),
            pytest.param(
                "Aenderungsantrag_EBD.xlsx",
                "my_favourite_ahb.xlsx",
                id="xlsx",
            ),
        ],
    )
    @pytest.mark.datafiles(
        "./unittests/testfiles/example_ahb.pdf",
        "./unittests/testfiles/Aenderungsantrag_EBD.xlsx",
    )
    async def test_file_download_file_does_not_exists_yet(
        self,
        mocker,
        tmpdir_factory,
        datafiles,
        file_name,
        expected_file_name,
    ):
        """
        Tests that a file can be downloaded and is stored if it does not exist before.
        """
        ees_dir = tmpdir_factory.mktemp("test_dir")
        ees_dir.mkdir("future")

        isfile_mocker = mocker.patch("edi_energy_scraper.os.path.isfile", return_value=False)
        with open(datafiles / file_name, "rb") as pdf_file:
            # Note that we do _not_ use pdf_file.read() here but provide the requests_mocker with a file handle.
            # Otherwise, you'd run into a "ValueError: Unable to determine whether fp is closed."
            # docs: https://requests-mock.readthedocs.io/en/latest/response.html?highlight=file#registering-responses
            with aioresponses() as mock:
                mock.get(
                    "https://my_file_link.inv/foo_bar",
                    body=pdf_file.read(),
                    headers={"Content-Disposition": f"attachment; filename={file_name}"},
                )
                ees = EdiEnergyScraper(
                    "https://my_file_link.inv/",
                    path_to_mirror_directory=ees_dir,
                )
                await ees._download_and_save_pdf(epoch=Epoch.FUTURE, file_basename="my_favourite_ahb", link="foo_bar")
        assert (ees_dir / "future" / expected_file_name).exists()
        isfile_mocker.assert_called_once_with(ees_dir / "future" / expected_file_name)

    @pytest.mark.parametrize(
        "metadata_has_changed",
        [
            pytest.param(
                True,
                id="metadata changed",
            ),
            pytest.param(
                False,
                id="metadata not changed",
            ),
        ],
    )
    @pytest.mark.datafiles(
        "./unittests/testfiles/example_ahb.pdf",
    )
    async def test_pdf_download_pdf_exists_already(
        self,
        mocker,
        tmpdir_factory,
        datafiles,
        metadata_has_changed: bool,
    ):
        """
        Tests that a PDF can be downloaded and is stored iff the metadata has changed.
        """
        ees_dir = tmpdir_factory.mktemp("test_dir")
        ees_dir.mkdir("future")

        isfile_mocker = mocker.patch("edi_energy_scraper.os.path.isfile", return_value=True)
        metadata_mocker = mocker.patch(
            "edi_energy_scraper.EdiEnergyScraper._have_different_metadata",
            return_value=metadata_has_changed,
        )
        remove_mocker = mocker.patch("edi_energy_scraper.os.remove")

        with open(datafiles / "example_ahb.pdf", "rb") as pdf_file:
            # Note that we do _not_ use pdf_file.read() here but provide the requests_mocker with a file handle.
            # Otherwise, you'd run into a "ValueError: Unable to determine whether fp is closed."
            # docs: https://requests-mock.readthedocs.io/en/latest/response.html?highlight=file#registering-responses
            with aioresponses() as mock:
                mock.get(
                    "https://my_file_link.inv/foo_bar.pdf",
                    body=pdf_file.read(),
                    headers={"Content-Disposition": 'attachment; filename="example_ahb.pdf"'},
                )
                ees = EdiEnergyScraper(
                    "https://my_file_link.inv/",
                    path_to_mirror_directory=ees_dir,
                )
                await ees._download_and_save_pdf(
                    epoch=Epoch.FUTURE, file_basename="my_favourite_ahb", link="foo_bar.pdf"
                )
        assert (ees_dir / "future/my_favourite_ahb.pdf").exists() == metadata_has_changed
        isfile_mocker.assert_called_once_with(ees_dir / "future/my_favourite_ahb.pdf")
        metadata_mocker.assert_called_once()

        if metadata_has_changed:
            remove_mocker.assert_called_once_with((ees_dir / "future/my_favourite_ahb.pdf"))

    @staticmethod
    def _get_soup_mocker(*args, **kwargs):
        if args[0] == "current.html":
            with open("./unittests/testfiles/current_20210210.html", "r", encoding="utf8") as infile_current:
                response_body = infile_current.read()
        elif args[0] == "past.html":
            with open("./unittests/testfiles/past_20210210.html", "r", encoding="utf8") as infile_past:
                response_body = infile_past.read()
        elif args[0] == "future.html":
            with open("./unittests/testfiles/future_20210210.html", "r", encoding="utf8") as infile_future:
                response_body = infile_future.read()
        elif args[0] == "https://www.edi-energy.de":
            with open("./unittests/testfiles/index_20210208.html", "r", encoding="utf8") as infile_index:
                response_body = infile_index.read()
        elif args[0] == "https://www.edi-energy.de/index.php?id=38":
            with open("./unittests/testfiles/dokumente_20210208.html", "r", encoding="utf8") as infile_docs:
                response_body = infile_docs.read()
        else:
            raise NotImplementedError(f"The soup for {args[0]} is not implemented in this test.")
        soup = BeautifulSoup(response_body, "html.parser")
        return soup

    @staticmethod
    def _get_efm_mocker(*args, **kwargs):
        heading = args[0].find("h2").text
        if heading == "Aktuell gültige Dokumente":
            return {"xyz": "/a_current_ahb.pdf"}
        if heading == "Zukünftige Dokumente":
            return {"def": "/a_future_ahb.xlsx"}
        if heading == "Archivierte Dokumente":
            return {"abc": "/a_past_ahb.pdf"}
        raise NotImplementedError(f"The case '{heading}' is not implemented in this test.")

    @pytest.mark.datafiles(
        "./unittests/testfiles/example_ahb.pdf",
        "./unittests/testfiles/example_ahb_2.pdf",
    )
    def test_have_different_metadata(self, datafiles):
        """Tests the function _have_different_metadata."""
        test_file = datafiles / "example_ahb.pdf"

        # Test that metadata of the same pdf returns same metadata
        with open(test_file, "rb") as same_pdf:
            has_changed = EdiEnergyScraper._have_different_metadata(same_pdf.read(), test_file)
            assert not has_changed

        # Test that metadata of a different pdf returns different metadata
        with open(datafiles / "example_ahb_2.pdf", "rb") as different_pdf:
            has_changed = EdiEnergyScraper._have_different_metadata(different_pdf.read(), test_file)
            assert has_changed

    def test_remove_no_longer_online_files(self, mocker):
        """Tests function remove_no_longer_online_files."""
        ees = EdiEnergyScraper(
            path_to_mirror_directory=Path("unittests/testfiles/removetest"),
        )
        assert (
            ees._root_dir / "future_20210210.html"
        ).exists()  # in general html wont be removed by the function under test
        path_example_ahb = ees._get_file_path("future", "example_ahb.pdf")
        path_example_ahb_2 = ees._get_file_path("future", "example_ahb_2.pdf")

        # Verify remove called
        remove_mocker = mocker.patch("edi_energy_scraper.os.remove")
        test_files_online = {path_example_ahb}
        ees.remove_no_longer_online_files(test_files_online)
        remove_mocker.assert_called_once_with(path_example_ahb_2)

        # Test nothing to remove
        remove_mocker_2 = mocker.patch("edi_energy_scraper.os.remove")
        test_files_online.add(path_example_ahb_2)
        ees.remove_no_longer_online_files(test_files_online)
        remove_mocker_2.assert_not_called()  # this also asserts that the lonely html file in removetest is not removed

    @pytest.mark.parametrize(
        "headers, file_basename, expected_file_name",
        [
            pytest.param(
                {"Content-Disposition": 'attachment; filename="example_ahb.pdf"'},
                "my_favourite_ahb",
                "my_favourite_ahb.pdf",
                id="pdf",
            ),
            pytest.param(
                {"Content-Disposition": 'attachment; filename="antrag.xlsx"'},
                "my_favourite_ahb",
                "my_favourite_ahb.xlsx",
                id="xlsx",
            ),
        ],
    )
    def test_add_file_extension_to_file_basename(self, headers, file_basename, expected_file_name):
        file_name_with_extension = EdiEnergyScraper._add_file_extension_to_file_basename(
            headers=headers, file_basename=file_basename
        )
        assert file_name_with_extension == expected_file_name

    @pytest.mark.datafiles(
        "./unittests/testfiles/example_ahb.pdf",
        "./unittests/testfiles/Aenderungsantrag_EBD.xlsx",
        "./unittests/testfiles/dokumente_20210208.html",
        "./unittests/testfiles/index_20210208.html",
        "./unittests/testfiles/current_20210210.html",
        "./unittests/testfiles/past_20210210.html",
        "./unittests/testfiles/future_20210210.html",
    )
    async def test_mirroring(self, mocker, tmpdir_factory, datafiles, caplog):
        """
        Tests the overall process and mocks most of the already tested methods.
        """
        ees_dir = tmpdir_factory.mktemp("test_dir_mirror")
        ees_dir.mkdir("future")
        ees_dir.mkdir("current")
        ees_dir.mkdir("past")
        ees_dir = Path(ees_dir)
        remove_no_longer_online_files_mocker = mocker.patch(
            "edi_energy_scraper.EdiEnergyScraper.remove_no_longer_online_files"
        )
        mocker.patch(
            "edi_energy_scraper.EdiEnergyScraper.get_epoch_links",
            return_value={
                "current": "current.html",
                "future": "future.html",
                "past": "past.html",
            },
        )
        mocker.patch(
            "edi_energy_scraper.EdiEnergyScraper._get_soup",
            side_effect=TestEdiEnergyScraper._get_soup_mocker,
        )
        mocker.patch(
            "edi_energy_scraper.EdiEnergyScraper.get_epoch_file_map",
            side_effect=TestEdiEnergyScraper._get_efm_mocker,
        )
        with open(datafiles / "example_ahb.pdf", "rb") as pdf_file_current, open(
            datafiles / "Aenderungsantrag_EBD.xlsx", "rb"
        ) as file_future, open(datafiles / "example_ahb.pdf", "rb") as file_past:
            with aioresponses() as mock:
                mock.get(
                    "https://www.edi-energy.de/a_future_ahb.xlsx",
                    body=file_future.read(),
                    headers={"Content-Disposition": 'attachment; filename="Aenderungsantrag_EBD.xlsx"'},
                )
                mock.get(
                    "https://www.edi-energy.de/a_current_ahb.pdf",
                    body=pdf_file_current.read(),
                    headers={"Content-Disposition": 'attachment; filename="example_ahb.pdf"'},
                )
                mock.get(
                    "https://www.edi-energy.de/a_past_ahb.pdf",
                    body=file_past.read(),
                    headers={"Content-Disposition": 'attachment; filename="example_ahb.pdf"'},
                )
                ees = EdiEnergyScraper(path_to_mirror_directory=ees_dir)
                await ees.mirror()
        assert (ees_dir / "index.html").exists()
        assert (ees_dir / "future.html").exists()
        assert (ees_dir / "current.html").exists()
        assert (ees_dir / "past.html").exists()
        assert (ees_dir / "future" / "def.xlsx").exists()
        assert (ees_dir / "past" / "abc.pdf").exists()
        assert (ees_dir / "current" / "xyz.pdf").exists()

        test_new_file_paths: set = {
            (ees_dir / "future" / "def.xlsx"),
            (ees_dir / "past" / "abc.pdf"),
            (ees_dir / "current" / "xyz.pdf"),
        }
        remove_no_longer_online_files_mocker.assert_called_once_with(test_new_file_paths)
        assert "Downloaded index.html" in caplog.messages

    @pytest.mark.parametrize(
        "input_files, expected_results",
        [
            pytest.param(
                [
                    "AcknowledgementDocumentAWT-informatorischeLesefassung1.0c_20240331_20231001.xlsx",
                    "AcknowledgementDocumentAWT1.0c_20240331_20231001.pdf",
                    "AcknowledgementDocumentAWT1.0cKonsolidierteLesefassungmitFehlerkorrekturenStand15.09.2023_20240331_20231001.pdf",
                    "AcknowledgementDocumentFB1.0c_20240331_20231001.pdf",
                    "AcknowledgementDocumentXSD1.0c_20240331_20231001.xsd",
                    "ActivationDocumentAWT-informatorischeLesefassung1.1a_20240331_20231001.xlsx",
                    "ActivationDocumentAWT1.1a_20240331_20231001.pdf",
                    "ActivationDocumentFB1.1a_99991231_20231001.pdf",
                    "ActivationDocumentXSD1.1a_99991231_20231001.xsd",
                    "AllgemeineFestlegungen-informatorischeLesefassung6.0c_20240331_20231001.docx",
                    "AllgemeineFestlegungen6.0c_20240331_20231001.pdf",
                    "ÄnderungsantragEBD1.3_99991231_20230815.xlsx",
                    "ÄnderungshistoriezudenXML-DatenformatenfürdenRedispatch2.0-informatorischeLesefassung15.09.2023_20240331_20230915.xlsx",
                    "ÄnderungshistoriezudenXML-DatenformatenfürdenRedispatch2.015.09.2023_20240331_20230915.pdf",
                    "AnwendungsübersichtderPrüfidentifikatoren-informatorischeLesefassung2.2_20240331_20231001.xlsx",
                    "AnwendungsübersichtderPrüfidentifikatoren-informatorischeLesefassung2.2KonsolidierteLesefassungmitFehlerkorrekturenStand30.11.2023_20240331_20231130.xlsx",
                    "AnwendungsübersichtderPrüfidentifikatoren2.2_20240331_20231001.pdf",
                    "AnwendungsübersichtderPrüfidentifikatoren2.2KonsolidierteLesefassungmitFehlerkorrekturenStand30.11.2023_20240331_20231130.pdf",
                    "APERAKCONTRLAHB-informatorischeLesefassung2.3m_20240331_20231001.docx",
                    "APERAKCONTRLAHB2.3m_20240331_20231001.pdf",
                    "APERAKMIG-informatorischeLesefassung2.1h_99991231_20221001.docx",
                    "APERAKMIG2.1h_99991231_20221001.pdf",
                    "AS4-Profil1.0_99991231_20231001.pdf",
                    "AS4-Profil1.0KonsolidierteLesefassungmitFehlerkorrekturenStand29.09.2023_99991231_20231001.pdf",
                    "Beschaffungsanforderung_energetischerAusgleichAWT1.0a_99991231_20220401.pdf",
                    "Beschaffungsanforderung_energetischerAusgleichFB1.0a_99991231_20220401.pdf",
                    "Beschaffungsanforderung_energetischerAusgleichXSD1.0a_99991231_20231001.xsd",
                    "BeschaffungsvorbehaltAWT1.0a_99991231_20220401.pdf",
                    "BeschaffungsvorbehaltFB1.0a_99991231_20220401.pdf",
                    "BeschaffungsvorbehaltXSD1.0a_99991231_20231001.xsd",
                    "CodelistederArtikelnummernundArtikel-ID-informatorischeLesefassung5.4_20240331_20231001.docx",
                    "CodelistederArtikelnummernundArtikel-ID-informatorischeLesefassung5.4-AußerordentlicheVeröffentlichung_20240331_20231023.docx",
                    "CodelistederArtikelnummernundArtikel-ID5.4_20240331_20231001.pdf",
                    "CodelistederArtikelnummernundArtikel-ID5.4-AußerordentlicheVeröffentlichung_20240331_20231023.pdf",
                    "CodelistedereuropäischenLändercodes1.0_99991231_20171001.pdf",
                    "CodelistedereuropäischenLändercodes1.0KonsolidierteLesefassungmitFehlerkorrekturenStand30.03.2023_99991231_20230330.pdf",
                    "CodelistederKonfigurationen-informatorischeLesefassung1.1a_20240331_20231001.docx",
                    "CodelistederKonfigurationen-informatorischeLesefassung1.1aKonsolidierteLesefassungmitFehlerkorrekturenStand29.06.2023_20240331_20231001.docx",
                    "CodelistederKonfigurationen1.1a_20240331_20231001.pdf",
                    "CodelistederKonfigurationen1.1aKonsolidierteLesefassungmitFehlerkorrekturenStand29.06.2023_20240331_20231001.pdf",
                    "CodelistederOBIS-KennzahlenundMedien-informatorischeLesefassung2.5_20240331_20231001.docx",
                    "CodelistederOBIS-KennzahlenundMedien-informatorischeLesefassung2.5KonsolidierteLesefassungmitFehlerkorrekturenStand29.09.2023_20240331_20231001.docx",
                    "CodelistederOBIS-KennzahlenundMedien2.5_20240331_20231001.pdf",
                    "CodelistederOBIS-KennzahlenundMedien2.5KonsolidierteLesefassungmitFehlerkorrekturenStand29.09.2023_20240331_20231001.pdf",
                    "CodelistederStandardlastprofilenachTUMünchen-Verfahren1.1_99991231_20151001.pdf",
                    "CodelistederStandardlastprofilenachTUMünchen-Verfahren1.1KonsolidierteLesefassungmitFehlerkorrekturenStand22.05.2015_99991231_20151001.pdf",
                    "CodelistederTemperaturanbieter-informatorischeLesefassung1.0i_99991231_20220726.docx",
                    "CodelistederTemperaturanbieter1.0i_99991231_20220726.pdf",
                    "CodelistederZeitreihentypen1.1d_99991231_20211001.pdf",
                    "CodelistederZeitreihentypen1.1dKonsolidierteLesefassungmitFehlerkorrekturenStand16.07.2021_99991231_20211001.pdf",
                    "COMDISAHB-informatorischeLesefassung1.0d_20240331_20231001.docx",
                    "COMDISAHB-informatorischeLesefassung1.0dKonsolidierteLesefassungmitFehlerkorrekturenStand20.07.2023_20240331_20231001.docx",
                    "COMDISAHB1.0d_20240331_20231001.pdf",
                    "COMDISAHB1.0dKonsolidierteLesefassungmitFehlerkorrekturenStand20.07.2023_20240331_20231001.pdf",
                    "COMDISMIG-informatorischeLesefassung1.0c_20240331_20231001.docx",
                    "COMDISMIG1.0c_20240331_20231001.pdf",
                    "CONTRLMIG2.0b_99991231_20221001.pdf",
                    "CONTRLMIG2.0bKonsolidierteLesefassungmitFehlerkorrekturenStand06.12.2021_99991231_20221001.pdf",
                    "EinführungsszenarioBK6-20-1601.8_99991231_20221001.pdf",
                    "EinführungsszenariozuAS41.0_99991231_20231001.pdf",
                    "Entscheidungsbaum-DiagrammeundCodelisten-informatorischeLesefassung3.4_20240331_20231001.docx",
                    "Entscheidungsbaum-DiagrammeundCodelisten-informatorischeLesefassung3.4KonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.docx",
                    "Entscheidungsbaum-DiagrammeundCodelisten3.4_20240331_20231001.pdf",
                    "Entscheidungsbaum-DiagrammeundCodelisten3.4KonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.pdf",
                    "GruppierungenderEDI@EnergyDokumente2.1_99991231_20221001.pdf",
                    "HerkunftsnachweisregisterAHB-informatorischeLesefassung2.3c_20240331_20231001.docx",
                    "HerkunftsnachweisregisterAHB-informatorischeLesefassung2.3cKonsolidierteLesefassungmitFehlerkorrekturenStand19.06.2023_20240331_20231001.docx",
                    "HerkunftsnachweisregisterAHB2.3c_20240331_20231001.pdf",
                    "HerkunftsnachweisregisterAHB2.3cKonsolidierteLesefassungmitFehlerkorrekturenStand19.06.2023_20240331_20231001.pdf",
                    "IFTSTAAHB-informatorischeLesefassung2.0e_99991231_20231001.docx",
                    "IFTSTAAHB-informatorischeLesefassung2.0eKonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_99991231_20231212.docx",
                    "IFTSTAAHB2.0e_99991231_20231001.pdf",
                    "IFTSTAAHB2.0eKonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_99991231_20231212.pdf",
                    "IFTSTAMIG-informatorischeLesefassung2.0e_99991231_20231001.docx",
                    "IFTSTAMIG-informatorischeLesefassung2.0e-AußerordentlicheVeröffentlichung_99991231_20231001.docx",
                    "IFTSTAMIG2.0e_99991231_20231001.pdf",
                    "IFTSTAMIG2.0e-AußerordentlicheVeröffentlichung_99991231_20231001.pdf",
                    "INSRPTAHB1.1g_99991231_20221001.pdf",
                    "INSRPTAHB1.1gKonsolidierteLesefassungmitFehlerkorrekturenStand30.03.2023_99991231_20230330.pdf",
                    "INSRPTMIG1.1a_99991231_20221001.pdf",
                    "INSRPTMIG1.1aKonsolidierteLesefassungmitFehlerkorrekturenStand30.03.2023_99991231_20230330.pdf",
                    "INVOICMIG-informatorischeLesefassung2.8b_20240331_20231001.docx",
                    "INVOICMIG-informatorischeLesefassung2.8bKonsolidierteLesefassungmitFehlerkorrekturenStand19.06.2023_20240331_20231001.docx",
                    "INVOICMIG2.8b_20240331_20231001.pdf",
                    "INVOICMIG2.8bKonsolidierteLesefassungmitFehlerkorrekturenStand19.06.2023_20240331_20231001.pdf",
                    "INVOICREMADVAHB-informatorischeLesefassung2.5b_20240331_20231001.docx",
                    "INVOICREMADVAHB-informatorischeLesefassung2.5bKonsolidierteLesefassungmitFehlerkorrekturenStand23.10.2023_20240331_20231023.docx",
                    "INVOICREMADVAHB2.5b_20240331_20231001.pdf",
                    "INVOICREMADVAHB2.5bKonsolidierteLesefassungmitFehlerkorrekturenStand23.10.2023_20240331_20231023.pdf",
                    "KostenblattAWT1.0b_99991231_20230401.pdf",
                    "KostenblattFB1.0b_99991231_20230401.pdf",
                    "KostenblattFB1.0bKonsolidierteLesefassungmitFehlerkorrekturenStand19.01.2023_99991231_20230401.pdf",
                    "KostenblattXSD-informatorischeLesefassung1.0b_99991231_20230401.xsd",
                    "KostenblattXSD-informatorischeLesefassung1.0bKonsolidierteLesefassungmitFehlerkorrekturenStand19.01.2023_99991231_20230401.xsd",
                    "KostenblattXSD1.0b_99991231_20231001.xsd",
                    "MSCONSAHB-informatorischeLesefassung3.1c_20240331_20231001.docx",
                    "MSCONSAHB-informatorischeLesefassung3.1cKonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.docx",
                    "MSCONSAHB3.1c_20240331_20231001.pdf",
                    "MSCONSAHB3.1cKonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.pdf",
                    "MSCONSMIG-informatorischeLesefassung2.4b_20240331_20231001.docx",
                    "MSCONSMIG2.4b_20240331_20231001.pdf",
                    "NetworkConstraintDocumentAWT1.1_99991231_20220401.pdf",
                    "NetworkConstraintDocumentAWT1.1KonsolidierteLesefassungmitFehlerkorrekturenStand29.08.2023_99991231_20230829.pdf",
                    "NetworkConstraintDocumentFB1.1_99991231_20220401.pdf",
                    "NetworkConstraintDocumentFB1.1KonsolidierteLesefassungmitFehlerkorrekturenStand29.08.2023_99991231_20230829.pdf",
                    "NetworkConstraintDocumentXSD-informatorischeLesefassung1.1_99991231_20220401.xsd",
                    "NetworkConstraintDocumentXSD1.1_99991231_20231001.xsd",
                    "NetworkConstraintDocumentXSD1.1KonsolidierteLesefassungmitFehlerkorrekturenStand29.08.2023_99991231_20231001.xsd",
                    "ORDCHGMIG-informatorischeLesefassung1.1_99991231_20231001.docx",
                    "ORDCHGMIG1.1_99991231_20231001.pdf",
                    "ORDERSMIG-informatorischeLesefassung1.3_99991231_20231001.docx",
                    "ORDERSMIG-informatorischeLesefassung1.3-AußerordentlicheVeröffentlichung_99991231_20231001.docx",
                    "ORDERSMIG1.3_99991231_20231001.pdf",
                    "ORDERSMIG1.3-AußerordentlicheVeröffentlichung_99991231_20231001.pdf",
                    "ORDERSORDRSPAHBMaBiS-informatorischeLesefassung2.2c_99991231_20231001.docx",
                    "ORDERSORDRSPAHBMaBiS2.2c_99991231_20231001.pdf",
                    "ORDRSPMIG-informatorischeLesefassung1.3_99991231_20231001.docx",
                    "ORDRSPMIG-informatorischeLesefassung1.3-AußerordentlicheVeröffentlichung_99991231_20231001.docx",
                    "ORDRSPMIG1.3_99991231_20231001.pdf",
                    "ORDRSPMIG1.3-AußerordentlicheVeröffentlichung_99991231_20231001.pdf",
                    "PARTINAHB-informatorischeLesefassung1.0c_20240331_20231001.docx",
                    "PARTINAHB-informatorischeLesefassung1.0cKonsolidierteLesefassungmitFehlerkorrekturenStand29.09.2023_20240331_20231001.docx",
                    "PARTINAHB1.0c_20240331_20231001.pdf",
                    "PARTINAHB1.0cKonsolidierteLesefassungmitFehlerkorrekturenStand29.09.2023_20240331_20231001.pdf",
                    "PARTINMIG-informatorischeLesefassung1.0c_20240331_20231001.docx",
                    "PARTINMIG1.0c_20240331_20231001.pdf",
                    "PlannedResourceScheduleDocumentAWT-informatorischeLesefassung1.0c_99991231_20231001.xlsx",
                    "PlannedResourceScheduleDocumentAWT-informatorischeLesefassung1.0cKonsolidierteLesefassungmitFehlerkorrekturenStand15.09.2023_99991231_20231001.xlsx",
                    "PlannedResourceScheduleDocumentAWT1.0c_99991231_20231001.pdf",
                    "PlannedResourceScheduleDocumentAWT1.0cKonsolidierteLesefassungmitFehlerkorrekturenStand15.09.2023_99991231_20231001.pdf",
                    "PlannedResourceScheduleDocumentFB1.0c_99991231_20231001.pdf",
                    "PlannedResourceScheduleDocumentFB1.0cKonsolidierteLesefassungmitFehlerkorrekturenStand29.08.2023_99991231_20231001.pdf",
                    "PlannedResourceScheduleDocumentXSD1.0c_99991231_20231001.xsd",
                    "PlannedResourceScheduleDocumentXSD1.0cKonsolidierteLesefassungmitFehlerkorrekturenStand13.06.2023_99991231_20231001.xsd",
                    "PRICATAHB-informatorischeLesefassung2.0c_20240331_20231001.docx",
                    "PRICATAHB2.0c_20240331_20231001.pdf",
                    "PRICATMIG-informatorischeLesefassung2.0c_99991231_20231001.docx",
                    "PRICATMIG2.0c_99991231_20231001.pdf",
                    "QUOTESMIG-informatorischeLesefassung1.3_99991231_20231001.docx",
                    "QUOTESMIG-informatorischeLesefassung1.3KonsolidierteLesefassungmitFehlerkorrekturenStand19.06.2023_99991231_20231001.docx",
                    "QUOTESMIG1.3_99991231_20231001.pdf",
                    "QUOTESMIG1.3KonsolidierteLesefassungmitFehlerkorrekturenStand19.06.2023_99991231_20231001.pdf",
                    "RegelungenzumÜbertragungsweg1.6_20240331_20231001.pdf",
                    "RegelungenzumÜbertragungswegfürAS42.0_20240331_20231001.pdf",
                    "RegelungenzumÜbertragungswegfürAS42.0KonsolidierteLesefassungmitFehlerkorrekturenStand29.09.2023_20240331_20231001.pdf",
                    "REMADVMIG-informatorischeLesefassung2.9b_20240331_20231001.docx",
                    "REMADVMIG2.9b_20240331_20231001.pdf",
                    "REQOTEMIG-informatorischeLesefassung1.3_99991231_20231001.docx",
                    "REQOTEMIG1.3_99991231_20231001.pdf",
                    "REQOTEQUOTESORDERSORDRSPORDCHGAHB-informatorischeLesefassung2.2_99991231_20231001.docx",
                    "REQOTEQUOTESORDERSORDRSPORDCHGAHB-informatorischeLesefassung2.2-AußerordentlicheVeröffentlichung_99991231_20231001.docx",
                    "REQOTEQUOTESORDERSORDRSPORDCHGAHB2.2_99991231_20231001.pdf",
                    "REQOTEQUOTESORDERSORDRSPORDCHGAHB2.2-AußerordentlicheVeröffentlichung_99991231_20231001.pdf",
                    "StammdatenAWT-informatorischeLesefassung1.2a_20240331_20231001.xlsx",
                    "StammdatenAWT1.2a_20240331_20231001.pdf",
                    "StammdatenFB1.2a_20240331_20231001.pdf",
                    "StammdatenXSD1.2a_20240331_20231001.xsd",
                    "StatusRequest_MarketDocumentAWT1.0_99991231_20230401.pdf",
                    "StatusRequest_MarketDocumentFB1.0_99991231_20230401.pdf",
                    "StatusRequest_MarketDocumentXSD-informatorischeLesefassung1.0_99991231_20230401.xsd",
                    "StatusRequest_MarketDocumentXSD1.0_99991231_20231001.xsd",
                    "Unavailability_MarketDocumentAWT-informatorischeLesefassung1.0c_20240331_20231001.xlsx",
                    "Unavailability_MarketDocumentAWT1.0c_20240331_20231001.pdf",
                    "Unavailability_MarketDocumentFB1.0c_20240331_20231001.pdf",
                    "Unavailability_MarketDocumentFB1.0cKonsolidierteLesefassungmitFehlerkorrekturenStand13.06.2023_20240331_20231001.pdf",
                    "Unavailability_MarketDocumentXSD1.0c_20240331_20231001.xsd",
                    "Unavailability_MarketDocumentXSD1.0cKonsolidierteLesefassungmitFehlerkorrekturenStand13.06.2023_20240331_20231001.xsd",
                    "UTILMDAHBGas-informatorischeLesefassung1.0a_99991231_20231001.docx",
                    "UTILMDAHBGas-informatorischeLesefassung1.0aKonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_99991231_20231212.docx",
                    "UTILMDAHBGas1.0a_99991231_20231001.pdf",
                    "UTILMDAHBGas1.0aKonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_99991231_20231212.pdf",
                    "UTILMDAHBMaBiS-informatorischeLesefassung4.1_20240331_20231001.docx",
                    "UTILMDAHBMaBiS-informatorischeLesefassung4.1KonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.docx",
                    "UTILMDAHBMaBiS4.1_20240331_20231001.pdf",
                    "UTILMDAHBMaBiS4.1KonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.pdf",
                    "UTILMDAHBStrom-informatorischeLesefassung1.1_20240331_20231001.docx",
                    "UTILMDAHBStrom-informatorischeLesefassung1.1KonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.docx",
                    "UTILMDAHBStrom1.1_20240331_20231001.pdf",
                    "UTILMDAHBStrom1.1KonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.pdf",
                    "UTILMDMIGGas-informatorischeLesefassungG1.0a_99991231_20231001.docx",
                    "UTILMDMIGGas-informatorischeLesefassungG1.0aKonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_99991231_20231212.docx",
                    "UTILMDMIGGasG1.0a_99991231_20231001.pdf",
                    "UTILMDMIGGasG1.0aKonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_99991231_20231212.pdf",
                    "UTILMDMIGStrom-informatorischeLesefassungS1.1_20240331_20231001.docx",
                    "UTILMDMIGStrom-informatorischeLesefassungS1.1KonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.docx",
                    "UTILMDMIGStromS1.1_20240331_20231001.pdf",
                    "UTILMDMIGStromS1.1KonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.pdf",
                    "UTILTSAHBBerechnungsformel-informatorischeLesefassung1.0e_20240331_20231001.docx",
                    "UTILTSAHBBerechnungsformel1.0e_20240331_20231001.pdf",
                    "UTILTSAHBDefinitionen-informatorischeLesefassung1.1_20240331_20231001.docx",
                    "UTILTSAHBDefinitionen-informatorischeLesefassung1.1KonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.docx",
                    "UTILTSAHBDefinitionen1.1_20240331_20231001.pdf",
                    "UTILTSAHBDefinitionen1.1KonsolidierteLesefassungmitFehlerkorrekturenStand12.12.2023_20240331_20231212.pdf",
                    "UTILTSMIG-informatorischeLesefassung1.1b_20240331_20231001.docx",
                    "UTILTSMIG1.1b_20240331_20231001.pdf",
                ],
                [
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.APERAK, EdifactFormat.CONTRL]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.APERAK, EdifactFormat.CONTRL]),
                    (EdifactFormatVersion.FV2210, [EdifactFormat.APERAK]),
                    (EdifactFormatVersion.FV2210, [EdifactFormat.APERAK]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2110, [None]),
                    (EdifactFormatVersion.FV2110, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2110, [None]),
                    (EdifactFormatVersion.FV2110, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2104, [None]),
                    (EdifactFormatVersion.FV2210, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2104, [None]),
                    (EdifactFormatVersion.FV2104, [None]),
                    (EdifactFormatVersion.FV2110, [None]),
                    (EdifactFormatVersion.FV2110, [None]),
                    (EdifactFormatVersion.FV2110, [None]),
                    (EdifactFormatVersion.FV2110, [None]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.COMDIS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.COMDIS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.COMDIS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.COMDIS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.COMDIS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.COMDIS]),
                    (EdifactFormatVersion.FV2210, [EdifactFormat.CONTRL]),
                    (EdifactFormatVersion.FV2210, [EdifactFormat.CONTRL]),
                    (EdifactFormatVersion.FV2210, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2210, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.IFTSTA]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.IFTSTA]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.IFTSTA]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.IFTSTA]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.IFTSTA]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.IFTSTA]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.IFTSTA]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.IFTSTA]),
                    (EdifactFormatVersion.FV2210, [EdifactFormat.INSRPT]),
                    (EdifactFormatVersion.FV2210, [EdifactFormat.INSRPT]),
                    (EdifactFormatVersion.FV2210, [EdifactFormat.INSRPT]),
                    (EdifactFormatVersion.FV2210, [EdifactFormat.INSRPT]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.INVOIC]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.INVOIC]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.INVOIC]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.INVOIC]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.INVOIC, EdifactFormat.REMADV]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.INVOIC, EdifactFormat.REMADV]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.INVOIC, EdifactFormat.REMADV]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.INVOIC, EdifactFormat.REMADV]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.MSCONS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.MSCONS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.MSCONS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.MSCONS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.MSCONS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.MSCONS]),
                    (EdifactFormatVersion.FV2110, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2110, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2110, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDCHG]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDCHG]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDERS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDERS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDERS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDERS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDERS, EdifactFormat.ORDRSP]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDERS, EdifactFormat.ORDRSP]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDRSP]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDRSP]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDRSP]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.ORDRSP]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.PARTIN]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.PARTIN]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.PARTIN]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.PARTIN]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.PARTIN]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.PARTIN]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.PRICAT]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.PRICAT]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.PRICAT]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.PRICAT]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.QUOTES]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.QUOTES]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.QUOTES]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.QUOTES]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.REMADV]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.REMADV]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.REQOTE]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.REQOTE]),
                    (
                        EdifactFormatVersion.FV2310,
                        [
                            EdifactFormat.ORDCHG,
                            EdifactFormat.ORDERS,
                            EdifactFormat.ORDRSP,
                            EdifactFormat.QUOTES,
                            EdifactFormat.REQOTE,
                        ],
                    ),
                    (
                        EdifactFormatVersion.FV2310,
                        [
                            EdifactFormat.ORDCHG,
                            EdifactFormat.ORDERS,
                            EdifactFormat.ORDRSP,
                            EdifactFormat.QUOTES,
                            EdifactFormat.REQOTE,
                        ],
                    ),
                    (
                        EdifactFormatVersion.FV2310,
                        [
                            EdifactFormat.ORDCHG,
                            EdifactFormat.ORDERS,
                            EdifactFormat.ORDRSP,
                            EdifactFormat.QUOTES,
                            EdifactFormat.REQOTE,
                        ],
                    ),
                    (
                        EdifactFormatVersion.FV2310,
                        [
                            EdifactFormat.ORDCHG,
                            EdifactFormat.ORDERS,
                            EdifactFormat.ORDRSP,
                            EdifactFormat.QUOTES,
                            EdifactFormat.REQOTE,
                        ],
                    ),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2304, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [None]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILMD]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILTS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILTS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILTS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILTS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILTS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILTS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILTS]),
                    (EdifactFormatVersion.FV2310, [EdifactFormat.UTILTS]),
                ],
                id="All",
            ),
        ],
    )
    def test_get_edifact_format(
        self, input_files: list[str], expected_results: list[tuple[EdifactFormatVersion, Optional[EdifactFormat]]]
    ):
        """
        Tests the determination of the edifact format and version for given files
        """
        results = []
        ees = EdiEnergyScraper()
        for file in input_files:
            results.append(ees.get_edifact_format(Path(file)))

        assert results == expected_results
