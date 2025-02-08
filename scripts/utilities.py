"""A collection of common utility functions.

* save_mpl_fig (I/O) 
* split_dataframe
* split_dataframe2
* save_excelsheet (I/O)
* pandas_to_tex (I/O)
* pprint_dict
* save_json (I/O)
* save_jsongz (I/O)
* read_json (I/O)
* read_jsons (I/O)
* read_jsongz (I/O)
* read_jsongzs (I/O)
* get_datestr_list
* normalize_str
* unix2datetime
* read_yaml (I/O)
* save_dict_to_yaml (I/O)
* save_svg_as_png (I/O)
* change_barwidth (mpl)
* text_to_list (I/O
* format_tiny_pval_expoential
"""

import gzip
import io
import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Union

try:
    import cairosvg
except ModuleNotFoundError:
    pass
import matplotlib.pyplot as plt
try:
    import msoffcrypto
except ModuleNotFoundError:
    pass
import numpy as np
import pandas as pd
import pytz
import yaml
from matplotlib.pyplot import Axes
from PIL import Image
from tableone import TableOne

def extract_emails(text: Optional[str]) -> List[str]:
    """
    Extract all email addresses from a text string.
    
    Args:
        text: String that may contain email addresses
        
    Returns:
        List of extracted email addresses
    """
    if pd.isna(text):
        return []
        
    # Regular expression for matching email addresses
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    # Find all matches
    emails = re.findall(email_pattern, text)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_emails = [x for x in emails if not (x in seen or seen.add(x))]
    
    return unique_emails

def clean_contact_column(df: pd.DataFrame, contact_col: str = 'contact') -> pd.DataFrame:
    """
    Clean contact column and create long format DataFrame with one email per row.
    
    Args:
        df: Input DataFrame
        contact_col: Name of the column containing contact information
        
    Returns:
        DataFrame in long format with one email per row
    """
    # Extract emails into lists
    df['email'] = df[contact_col].apply(extract_emails)
    
    # Explode the emails column to create one row per email
    df_long = df.explode('email').reset_index(drop=True)
    
    return df_long

def save_mpl_fig(
    savepath: str, formats: Optional[Iterable[str]] = None, dpi: Optional[int] = None
) -> None:
    """Save matplotlib figures to ../output.

    Will handle saving in png and in pdf automatically using the same file stem.

    Parameters
    ----------
    savepath: str
        Name of file to save to. No extensions.
    formats: Array-like
        List containing formats to save in. (By default 'png' and 'pdf' are saved).
        Do a:
            plt.gcf().canvas.get_supported_filetypes()
        or:
            plt.gcf().canvas.get_supported_filetypes_grouped()
        To see the Matplotlib-supported file formats to save in.
        (Source: https://stackoverflow.com/a/15007393)
    dpi: int
        DPI for saving in png.

    Returns
    -------
    None
    """
    # Save pdf
    plt.savefig(f"{savepath}.pdf", dpi=None, bbox_inches="tight", pad_inches=0)

    # save png
    plt.savefig(f"{savepath}.png", dpi=dpi, bbox_inches="tight", pad_inches=0)

    # Save additional file formats, if specified
    if formats:
        for format in formats:
            plt.savefig(
                f"{savepath}.{format}",
                dpi=None,
                bbox_inches="tight",
                pad_inches=0,
            )
    return None


def pandas_to_tex(
    df: pd.DataFrame, texfile: str, index: bool = False, escape=False, **kwargs: Any
) -> None:
    """Save a Pandas dataframe to a LaTeX table fragment.

    Uses the built-in .to_latex() function. Only saves table fragments
    (equivalent to saving with "fragment" option in estout).

    Parameters
    ----------
    df: Pandas DataFrame
        Table to save to tex.
    texfile: str
        Name of .tex file to save to.
    index: bool
        Save index (Default = False).
    kwargs: any
        Additional options to pass to .to_latex().

    Returns
    -------
    None
    """
    if texfile.split(".")[-1] != "tex":
        texfile += ".tex"

    tex_table = df.to_latex(index=index, header=False, escape=escape, **kwargs)
    tex_table_fragment = "\n".join(tex_table.split("\n")[2:-3])
    # Remove the last \\ in the tex fragment to prevent the annoying
    # "Misplaced \noalign" LaTeX error when I use \bottomrule
    # tex_table_fragment = tex_table_fragment[:-2]

    with open(texfile, "w") as tf:
        tf.write(tex_table_fragment)
    return None


def read_jsons(directory: str, extension: str = ".json") -> list:
    """
    Read multiple JSON files from a directory and return their contents as a list.

    Parameters
    ----------
    directory : str
        The path to the directory containing the JSON files.

    Returns
    -------
    List[dict]
        A list containing the contents of the JSON files.

    Raises
    ------
    FileNotFoundError
        If the specified directory does not exist.
    NotADirectoryError
        If the specified path is not a directory.
    json.JSONDecodeError
        If any of the JSON files are malformed.

    Example
    -------
    >>> import os
    >>> import json
    >>> # Create a temporary directory and JSON file for testing
    >>> temp_dir = "temp_directory"
    >>> os.mkdir(temp_dir)
    >>> json_data = {"name": "John", "age": 30}, {"name": "Alice", "age": 25}
    >>> json_file = os.path.join(temp_dir, "example.json")
    >>> with open(json_file, "w") as f:
    ...     json.dump(json_data, f)
    >>> # Call the function to read the JSON files
    >>> read_jsons(temp_dir)
    [[{'name': 'John', 'age': 30}, {'name': 'Alice', 'age': 25}]]
    >>> # Clean up the temporary directory and file
    >>> os.remove(json_file)
    >>> os.rmdir(temp_dir)
    """
    data_list = []
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path) and filename.endswith(extension):
            data_list.append(read_json(file_path))
    return data_list


def clean_email_column_no_dedupe(df, column_name="email"):
    """
    Cleans the specified email column in a DataFrame by:
    1. Stripping whitespace, converting to lowercase, and removing commas.
    2. Dropping rows where the email contains only a single letter or symbol.
    3. Dropping rows where the email is NaN.
    4. Valid email
    5. Dedupe (keeping first)

    Args:
        df (pd.DataFrame): The DataFrame to clean.
        column_name (str): The column to process (default: "email").

    Returns:
        pd.DataFrame: Cleaned DataFrame (modification done safely).
    """
    if column_name in df.columns:
        df = df.copy()
        df[column_name] = df[column_name].str.strip().str.lower().str.replace(",", "", regex=True).str.replace(" ", "")
        df = df[~df[column_name].str.match(r"^[A-Za-z,_-]$", na=False)]
        df = df.dropna(subset=[column_name])
        
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

        df = df[df[column_name].str.match(email_regex, na=False)]
        
        df = df.drop_duplicates(subset=["email"], keep="first", ignore_index=True)

    return df


def process_json_files_to_matrix(json_folder):
    """
    Process JSON files and create a matrix of filenames vs names present in files.
    
    Args:
        json_folder (str): Path to folder containing JSON files
        
    Returns:
        pd.DataFrame: Matrix with filenames as rows and all unique names as columns.
                     Values are boolean indicating if name is present in file.
    """
    
    all_names = set()
    file_list = [f for f in os.listdir(json_folder) if f.endswith(".json")]

    for filename in file_list:
        file_path = os.path.join(json_folder, filename)
        with open(file_path, "r") as file:
            try:
                data = json.load(file)
                
                if isinstance(data, dict):
                    data = [data]
                elif not isinstance(data, list):
                    data = []
                
                # Extract names
                all_names.update(entry["Name"] for entry in data if isinstance(entry, dict) and "Name" in entry)
            except (json.JSONDecodeError, TypeError):
                pass
    
    all_names = sorted(all_names)

    df = pd.DataFrame(columns=["Filename"] + all_names)

    for filename in file_list:
        file_path = os.path.join(json_folder, filename)
        with open(file_path, "r") as file:
            try:
                data = json.load(file)
                
                # Ensure data is a list
                if isinstance(data, dict):
                    data = [data]
                elif not isinstance(data, list):
                    data = []

                present_names = {entry["Name"] for entry in data if isinstance(entry, dict) and "Name" in entry}
            except (json.JSONDecodeError, TypeError):
                present_names = set()
        
        row = {"Filename": filename.replace(".json", "")}
        row.update({name: name in present_names for name in all_names})
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

    return df    
