"""Leitura uniforme de planilhas .xls e .xlsx como grade de valores."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import openpyxl
import xlrd

Grid = list[list[Any]]


class WorkbookError(ValueError):
    """Planilha que não abre ou não tem a aba esperada."""


def sheet_names(path: Path) -> list[str]:
    try:
        if path.suffix.lower() == ".xlsx":
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            try:
                return list(wb.sheetnames)
            finally:
                wb.close()
        book = xlrd.open_workbook(str(path), on_demand=True)
        try:
            return list(book.sheet_names())
        finally:
            book.release_resources()
    except Exception as exc:  # formatos corrompidos levantam erros variados
        raise WorkbookError(f"não abre: {type(exc).__name__}: {exc}") from exc


def read_sheet(path: Path, sheet: str, max_rows: int | None = None) -> Grid:
    """Valores de uma aba; datas do .xls viram `datetime`, como no .xlsx."""
    try:
        if path.suffix.lower() == ".xlsx":
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            try:
                return [
                    list(row) for row in wb[sheet].iter_rows(max_row=max_rows, values_only=True)
                ]
            finally:
                wb.close()
        book = xlrd.open_workbook(str(path), on_demand=True)
        try:
            sh = book.sheet_by_name(sheet)
            rows = sh.nrows if max_rows is None else min(max_rows, sh.nrows)
            grid: Grid = []
            for r in range(rows):
                values: list[Any] = []
                for c in range(sh.ncols):
                    cell = sh.cell(r, c)
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        try:
                            values.append(xlrd.xldate_as_datetime(cell.value, book.datemode))
                        except (ValueError, OverflowError):
                            values.append(cell.value)
                    elif cell.ctype in (
                        xlrd.XL_CELL_EMPTY,
                        xlrd.XL_CELL_BLANK,
                        xlrd.XL_CELL_ERROR,
                    ):
                        values.append(None)
                    else:
                        values.append(cell.value)
                grid.append(values)
            return grid
        finally:
            book.release_resources()
    except KeyError as exc:
        raise WorkbookError(f"sem a aba {sheet!r}") from exc
    except WorkbookError:
        raise
    except Exception as exc:
        raise WorkbookError(f"não abre: {type(exc).__name__}: {exc}") from exc


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    return str(value).strip()
