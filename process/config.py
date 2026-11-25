from openpyxl import load_workbook

godkendte_organisationer: set[str] = set()


def get_godkendte_organisationer() -> set[str]:
    """Henter listen over godkendte organisationer"""
    if not godkendte_organisationer:
        raise ValueError(
            "Godkendte organisationer er ikke indlæst, brug load_godkendte_organisationer først"
        )
    return godkendte_organisationer


def load_godkendte_organisationer(file_path: str):
    """Indlæser godkendte organisationer fra første kolonne i Excel-filen (række 1 er overskrift)"""
    global godkendte_organisationer
    try:
        workbook = load_workbook(file_path, read_only=True)
        worksheet = workbook.active

        if worksheet is None:
            raise ValueError("Worksheet could not be loaded")

        organisationer: set[str] = set()
        for row in worksheet.iter_rows(min_row=2, max_col=1, values_only=True):
            if row[0] and str(row[0]).strip():
                organisationer.add(str(row[0]).strip())

        workbook.close()

        if not organisationer:
            raise ValueError("Ingen organisationer fundet i filen")

        godkendte_organisationer = organisationer

    except Exception as e:
        raise RuntimeError(
            f"Failed to load approved organizations from Excel file '{file_path}': {str(e)}"
        ) from e
