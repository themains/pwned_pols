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


def split_dataframe(dataframe: pd.DataFrame, chunk_size: int) -> list:
    """Split a dataframe into chunks of 'chunk_size'.

    From https://stackoverflow.com/a/28882020.

    Parameters
    ----------
    dataframe : pd.DataFrame
        Dataframe to be chunked.
    chunk_size : int
        Size of each chunk.

    Returns
    -------
    List
        List of chunked dataframes.
    """
    chunks = list()
    num_chunks = (len(dataframe) // chunk_size) + 1
    for i in range(num_chunks):
        chunks.append(dataframe[i * chunk_size : (i + 1) * chunk_size])
    return chunks


def split_dataframe2(dataframe: pd.DataFrame, n_chunks: int) -> list:
    """Split a dataframe into n chunks.

    Parameters
    ----------
    dataframe : pd.DataFrame
        Dataframe to be chunked.
    n_chunks : int
        How many chunks.

    Returns
    -------
    List
        List of chunked dataframes
    """
    # calculate the approximate chunk size
    chunk_size = len(dataframe) // n_chunks

    # split the dataframe into chunks
    chunks = [
        dataframe[i : i + chunk_size] for i in range(0, len(dataframe), chunk_size)
    ]

    if len(chunks) > n_chunks:  # More chunks than specified, b/c of remainder rows
        # Concatenate the last two chunks
        chunks = chunks[:-2] + [pd.concat([chunks[-2], chunks[-1]])]
    return chunks


def save_excelsheet(
    filepath: str, sheetname: str, table: pd.DataFrame, **kwargs: Any
) -> None:
    """
    Save Pandas DataFrame to Excel sheet, handling I/O and replacing existing sheets and files.

    Parameters
    ----------
    filepath : str
        Filepath of the Excel file.
    sheetname : str
        Name of the sheet to write the DataFrame to.
    table : pd.DataFrame
        DataFrame to be saved to Excel.
    **kwargs : Any
        Additional keyword arguments to be passed to pd.DataFrame.to_excel().

    Returns
    -------
    None
    """
    try:
        with pd.ExcelWriter(filepath, mode="a", if_sheet_exists="replace") as writer:
            table.to_excel(writer, sheet_name=sheetname, index=False, **kwargs)
    except:
        table.to_excel(filepath, sheet_name=sheetname, index=False, **kwargs)
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


def tableone_to_texfrag(tableone: TableOne, texfile: str) -> None:
    r"""
    Convert a TableOne object to a LaTeX table fragment and save it to a file.

    Parameters
    ----------
    tableone : tableone.TableOne
        The TableOne object to convert to LaTeX.
    texfile : str
        The name or path of the output LaTeX file.

    Returns
    -------
    None

    Description
    -----------
    This function takes a TableOne object, generates a LaTeX table fragment
    using the 'latex' table format, and saves it to a specified file.

    The generated LaTeX table fragment will include the table body without
    the table environment commands (\begin{tabular}, \end{tabular}),
    the headers, and the top and bottom horizontal lines.

    The function removes the last '\\' in the LaTeX fragment to prevent
    the "Misplaced \noalign" LaTeX error when using \bottomrule.

    The function will append the '.tex' extension to the texfile if it is
    not already present. If the file already exists, it will be overwritten.
    """
    tex_table = tableone.tabulate(tablefmt="latex")
    # line #1 = \begin{tabular}...
    # line #2 = headers..
    # line #3 = \hline
    # last line = \end{tabular}
    # 2nd last line = \hline
    tex_table_fragment = "\n".join(tex_table.split("\n")[4:-2])
    # Remove the last \\ in the tex fragment to prevent the annoying
    # "Misplaced \noalign" LaTeX error when I use \bottomrule
    tex_table_fragment = tex_table_fragment[:-2]
    # Save
    if texfile.split(".")[-1] != "tex":
        texfile += ".tex"
    with open(texfile, "w") as tf:
        tf.write(tex_table_fragment)
    return None


def pprint_dict(data: Dict, indent: int = 2) -> None:
    """Pretty prints a dictionary.

    Parameters
    ----------
    data : dict
        The dictionary to be pretty printed.
    indent: int
        Number of indent spaces per line.

    Returns
    -------
    None
        This function doesn't return anything.

    Examples
    --------
    >>> sample_dict = {
    ...     "name": "John Doe",
    ...     "age": 30,
    ...     "city": "New York"
    ... }
    >>> pprint_dict(sample_dict)
    {
      "name": "John Doe",
      "age": 30,
      "city": "New York"
    }
    """
    # Convert the dictionary to a JSON string
    try:
        json_data = json.dumps(data, indent=indent)
    except TypeError:
        json_data = json.dumps(dict(data), indent=indent)

    # Pretty print the JSON data
    print(json_data)

    return None


def save_json(data, savepath):
    """
    Save a JSON object to a file.

    Parameters
    ----------
    data : dict
        The JSON object to be saved.
    file_path : str
        The path to the file where the JSON object will be saved.

    Returns
    -------
    None

    Example
    -------
    >>> import json
    >>> # Define the JSON data and save path
    >>> json_data = {"name": "John", "age": 30}
    >>> json_file = "example.json"
    >>> # Call the function to save the JSON object
    >>> save_json(json_data, json_file)
    >>> # Read the saved JSON file
    >>> with open(json_file) as f:
    ...     saved_data = json.load(f)
    >>> saved_data
    {'name': 'John', 'age': 30}
    >>> # Clean up the temporary file
    >>> import os
    >>> os.remove(json_file)
    """
    if savepath.split(".")[-1] != "json":
        savepath += ".json"
    with open(savepath, "w") as file:
        json.dump(data, file)
    return None


def save_jsongz(data: dict, filename: str) -> None:
    """
    Compresses and saves a Python dictionary to a JSON file in gzip format.

    Parameters
    ----------
    data : Dict
        The dictionary to be saved as JSON.
    filename : str
        The name of the output file. Should have a ".json.gz" extension.

    Returns
    -------
    None

    Raises
    ------
    FileNotFoundError
        If the specified directory path does not exist.
    """
    with gzip.open(filename, "wt") as f:
        json.dump(data, f)
    return None


def read_json(file_path: str) -> dict:
    """Read a JSON file and return its contents as a dictionary.

    Parameters
    ----------
    file_path: str
        The path to the JSON file.

    Returns
    -------
    Dict
        The contents of the JSON file as a dictionary.

    Raises:
        FileNotFoundError: If the file specified by file_path does not exist.
        json.JSONDecodeError: If the JSON file is malformed.

    Example
    -------
    >>> import json
    >>> # Create a temporary JSON file for testing
    >>> json_data = {"name": "John", "age": 30}
    >>> json_file = "example.json"
    >>> with open(json_file, "w") as f:
    ...     json.dump(json_data, f)
    >>> # Call the function to read the JSON file
    >>> read_json(json_file)
    {'name': 'John', 'age': 30}
    >>> # Clean up the temporary file
    >>> import os
    >>> os.remove(json_file)
    """
    if file_path.split(".")[-1] != "json":
        file_path += ".json"
    with open(file_path) as file:
        data = json.load(file)
    return data


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


def read_jsongz(filepath: str) -> Dict:
    """
    Read a JSON file compressed with gzip.

    Parameters
    ----------
    cache_filepath: str
        The path to the gzip-compressed JSON file.

    Returns
    -------
    dict
        The loaded metadata as a dictionary.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON data.
        gzip.BadGzipFile: If the file is not a valid gzip file.
    """
    with gzip.open(filepath, "r") as f:
        payload = json.loads(f.read())
    return payload


def read_jsongzs(directory: str, extension: str = ".json.gz") -> list:
    """
    Read multiple gzipped JSON files from a directory and return their contents as a list.

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
    """
    data_list = []
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path) and filename.endswith(extension):
            data_list.append(read_jsongz(file_path))
    return data_list


def get_datestr_list(start_date: str, end_date: str) -> List[str]:
    """Generate a list of dates in string format between two specified dates.

    Parameters
    ----------
    start_date : str
        The start date in the format 'YYYY-MM-DD'.
    end_date : str
        The end date in the format 'YYYY-MM-DD'.

    Returns
    -------
    List[str]
        A list of dates in string format between the start and end dates (inclusive).

    Example
    -------
    >>> start_date = "2022-01-01"
    >>> end_date = "2022-01-05"
    >>> dates = get_datestr_list(start_date, end_date)
    >>> print(dates)
    ['2022-01-01', '2022-01-02', '2022-01-03', '2022-01-04', '2022-01-05']
    """
    dates = []
    date_format = "%Y-%m-%d"

    start = datetime.strptime(start_date, date_format)
    end = datetime.strptime(end_date, date_format)

    current_date = start
    while current_date <= end:
        dates.append(current_date.strftime(date_format))
        current_date += timedelta(days=1)

    return dates


def normalize_str(name: str, glue: str = "-") -> str:
    """
    Normalize a string by replacing consecutive dashes, underscores, or dots with a single dash and converting it to lowercase.

    Parameters
    ----------
    name : str
        The string to normalize.
    glue : str
        How to stitch tokens together. Default is dash "-". E.g.
        foo-bar.

    Returns
    -------
    str
        The normalized string.

    Examples
    --------
    >>> normalize_str("0riion_py-sls-lambda-toolkit", glue="_")
    '0riion_py_sls_lambda_toolkit'
    >>> normalize_str("Abx.asd", glue="_")
    'abx_asd'
    >>> normalize_str("file_____slug", glue="_")
    'file_slug'
    """
    return re.sub(r"[-_.]+", glue, name).lower()


def unix2datetime(timestamp: Union[str, int, float], timezone: str = "UTC") -> str:
    """
    Convert a Unix timestamp to a human-readable date string.

    Parameters
    ----------
    timestamp : int
        The Unix timestamp to convert.
    timezone : str, optional
        The timezone to use for the conversion (default is "UTC").

    Examples
    --------
    >>> unix2datetime("1687312132", 'Singapore')
    '2023-06-21 09:48:52'

    >>> unix2datetime("1687312132", 'Asia/Tokyo')
    '2023-06-21 10:48:52'

    >>> unix2datetime(1687312132)
    '2023-06-21 01:48:52'

    Returns
    -------
    str
        A string representing the human-readable date in the format 'YYYY-MM-DD HH:MM:SS'.
    """
    if isinstance(timestamp, str):
        timestamp = int(timestamp)

    # Divide by 1000 if the timestamp is in milliseconds
    if len(str(timestamp)) > 10:
        timestamp = timestamp / 1000

    # Create a datetime object from the timestamp
    date = datetime.fromtimestamp(timestamp, tz=pytz.timezone(timezone))

    # Convert the datetime object to a human-readable string format
    human_readable_date = date.strftime("%Y-%m-%d %H:%M:%S")

    return human_readable_date


def read_yaml(filename: str) -> dict:
    """
    Read a YAML file.

    Parameters
    ----------
    filename : str
        The path to the YAML file.

    Returns
    -------
    Dict[str, str]
        A dictionary where the keys are natural types and the values are categories.
    """
    with open(filename, "r") as file:
        data = yaml.safe_load(file)
    return data


def read_encrypted_excel(
    filepath: str, password: str, sheet_name: str = "Sheet1"
) -> pd.DataFrame:
    """
    Read data from a password-protected Excel file using the msoffcrypto library.

    Parameters
    ----------
    filepath : str
        The path to the password-protected Excel file.
    password : str
        The password to unlock the protected Excel file.
    sheet_name : str, optional
        The name of the sheet to read. Default is 'Sheet1'.

    Returns
    -------
    pd.DataFrame
        The DataFrame containing the data from the specified sheet,
        or None if an error occurs during the reading process.
    """
    try:
        decrypted_workbook = io.BytesIO()

        with open(filepath, "rb") as file:
            office_file = msoffcrypto.OfficeFile(file)
            office_file.load_key(password=password)
            office_file.decrypt(decrypted_workbook)

        df = pd.read_excel(decrypted_workbook, sheet_name=sheet_name)
        return df
    except Exception as e:
        print(f"Error reading password-protected Excel: {e}")


def save_dict_to_yaml(dictionary: dict, file_path: str) -> None:
    """
    Save a Python dictionary to a YAML file.

    Parameters
    ----------
    dictionary : dict
        The dictionary to be saved to the YAML file.
    file_path : str
        The path and name of the YAML file to save the dictionary.

    Returns
    -------
    None

    Raises
    ------
    IOError
        If there is an error writing to the YAML file.
    """
    # Convert complex types to simpler ones
    # e.g., numpy.core.multiarray.scalar as a number
    for key, value in dictionary.items():
        if isinstance(value, np.generic):
            # Convert NumPy types to native Python types
            dictionary[key] = value.item()

    try:
        with open(file_path, "w") as file:
            yaml.dump(dictionary, file)
    except IOError as e:
        raise IOError(f"Error saving dictionary to YAML file: {e}")
    return None


def save_svg_as_png(svg_image: str, save_path: str, scale: int = 1) -> None:
    """
    Convert an SVG image to PNG format and save it to the specified path.

    Parameters
    ----------
    svg_image : str
        The SVG image data.
    save_path : str
        The path where the PNG image should be saved.
    scale: float
        Scale of image.

    Returns
    -------
    None
    """
    png_image = cairosvg.svg2png(bytestring=svg_image.encode(), scale=scale)
    image = Image.open(io.BytesIO(png_image))
    image.save(save_path)
    return None


def change_barwidth(ax: Axes, new_value: float) -> None:
    """
    Change the width of bars in a bar plot to a new value.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes object containing the bar plot.

    new_value : float
        The desired new width for the bars.

    Returns
    -------
    None

    Notes
    -----
    This function modifies the width of the bars in the given bar plot (`ax.patches`) to the specified `new_value`.
    The function adjusts the width and re-centers each bar by updating its x-position.

    Example
    -------
    _, ax = plt.subplots()
    sns.barplot(..., ax=ax)
    change_barwidth(ax, 0.5)
    """
    if not ax.patches:
        print("No bars found in the provided Axes object.")
        return

    for patch in ax.patches:
        if (
            hasattr(patch, "get_width")
            and hasattr(patch, "set_width")
            and hasattr(patch, "set_x")
            and hasattr(patch, "get_x")
        ):
            current_width = patch.get_width()
            diff = current_width - new_value
            patch.set_width(new_value)
            patch.set_x(patch.get_x() + diff * 0.5)
        else:
            print("The patch does not have the required methods to change width.")
    return None


def text_to_list(file_path: str) -> List[str]:
    """
    Read a text file and return its content as a list of lines.

    Parameters
    ----------
    file_path : str
        Path to the text file.

    Returns
    -------
    List[str]
        List containing the lines of the text file.
    """
    try:
        with open(file_path, "r") as file:
            lines = file.readlines()
            content_list = [line.strip() for line in lines]
            return content_list
    except FileNotFoundError:
        print(f"File '{file_path}' not found.")
        return []


def format_tiny_pval_exponential(num, pval_label="p-val"):
    """
    Format a p-value for display, using either rounded decimal or exponential notation.

    This function formats a p-value in a readable way for scientific reporting.
    For p-values >= 0.001, it rounds to three decimal places. For smaller p-values,
    it represents them in a specific exponential format.

    Parameters
    ----------
    num : float
        The p-value to be formatted.

    Returns
    -------
    str
        A string representation of the formatted p-value.

    Examples
    --------
    >>> format_tiny_pval_exponential(0.00026)
    'p-val < .001'
    >>> format_tiny_pval_exponential(0.000026)
    'p-val < .001e-1'
    >>> format_tiny_pval_exponential(0.0000026)
    'p-val < .001e-2'
    >>> format_tiny_pval_exponential(0.004)
    'p-val = .004'
    >>> format_tiny_pval_exponential(0.1)
    'p-val = .1'
    >>> format_tiny_pval_exponential(0.001)
    'p-val = .001'
    """
    if num >= 0.001:
        # Round the number to three decimal places
        rounded = round(num, 3)

        # Convert to string and strip the leading zero
        rounded_string = str(rounded).lstrip("0")

        # Return formatted string for p-values >= 0.001
        return f"{pval_label} = {rounded_string}"
    elif num >= 0.0001:
        return f"{pval_label} < .001"
    else:
        exponent = int(np.log10(num) - np.log10(0.001))

        # Return formatted string in exponential format
        return f"{pval_label} < .001e{exponent}"


def calculate_summary_statistics(
    data_df,
    groupby_column,
    value_column,
    percentiles=None,
    sort_order="count",
    custom_order=None,
    category_names=None,
):
    """
    Calculate summary statistics for a given DataFrame, including percentage of the total sample size.

    Parameters:
        data_df (DataFrame): The DataFrame containing the data.
        groupby_column (str): The column to group by.
        value_column (str): The column for which to calculate statistics.
        percentiles (list, optional): List of percentiles to calculate. Default is None.
        sort_order (str, optional): "count" to sort by count (highest first), "custom" for a user-defined order. Default is "count".
        custom_order (list, optional): Custom order of categories if sort_order is "custom". Default is None.
        category_names (dict, optional): Dictionary to map original category names to new display names. Default is None.

    Returns:
        DataFrame: A DataFrame with the summary statistics, including count and percentage of total.
    """
    if percentiles is None:
        percentiles = [25, 50, 75]

    # Calculate summary statistics
    summary_stats = data_df.groupby(groupby_column)[value_column].agg(
        count="size", mean="mean", std="std", min="min", max="max"
    )

    # Ensure count is an integer
    summary_stats["count"] = summary_stats["count"].astype(int)

    # Round mean and std to one decimal place
    summary_stats["mean"] = summary_stats["mean"].round(1)
    summary_stats["std"] = summary_stats["std"].round(1)

    # Calculate the percentage of the total sample size for each group
    total_count = len(data_df)
    summary_stats["percent"] = (summary_stats["count"] / total_count * 100).round(1)

    # Format the count and percentage together in the desired format
    summary_stats["count"] = summary_stats.apply(
        lambda row: f"{int(row['count'])} ({row['percent']}\%)", axis=1
    )
    summary_stats = summary_stats.drop(
        columns="percent"
    )  # Drop the intermediate percent column

    # Calculate percentile values
    percentile_values = (
        data_df.groupby(groupby_column)[value_column]
        .apply(lambda x: pd.Series(np.nanpercentile(x, percentiles), index=percentiles))
        .unstack()
        .round(1)
    )

    # Merge summary statistics and percentile values
    summary_with_percentiles = pd.merge(
        summary_stats, percentile_values, left_index=True, right_index=True
    )

    # Reorder columns
    desired_columns = ["count", "mean", "std", "min"] + percentiles + ["max"]
    summary_with_percentiles = summary_with_percentiles.reindex(
        columns=desired_columns
    ).reset_index()

    # Sort the DataFrame based on the selected sort_order
    if sort_order == "count":
        # Extract numeric part from count, convert to int, and sort by it
        summary_with_percentiles["count_value"] = summary_with_percentiles[
            "count"
        ].apply(lambda x: int(x.split()[0]))
        summary_with_percentiles = summary_with_percentiles.sort_values(
            by="count_value", ascending=False
        ).reset_index(drop=True)
        summary_with_percentiles = summary_with_percentiles.drop(
            columns="count_value"
        )  # Drop the helper column after sorting
    elif sort_order == "custom" and custom_order is not None:
        # Sort by the custom order provided by the user
        summary_with_percentiles[groupby_column] = pd.Categorical(
            summary_with_percentiles[groupby_column],
            categories=custom_order,
            ordered=True,
        )
        summary_with_percentiles = summary_with_percentiles.sort_values(
            by=groupby_column
        ).reset_index(drop=True)

    # Apply custom category names if provided
    if category_names:
        summary_with_percentiles[groupby_column] = summary_with_percentiles[
            groupby_column
        ].replace(category_names)

    return summary_with_percentiles        