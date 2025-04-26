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
* normalize_strc
* unix2datetime
* read_yaml (I/O)
* save_dict_to_yaml (I/O)
* save_svg_as_png (I/O)
* change_barwidth (mpl)
* text_to_list (I/O
* format_tiny_pval_expoential
"""

import json
import os
import re
from typing import Any, Iterable, List, Optional

import matplotlib.pyplot as plt
import pandas as pd
from email_validator import validate_email, EmailNotValidError, caching_resolver


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
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    # Find all matches
    emails = re.findall(email_pattern, text)

    # Remove duplicates while preserving order
    seen = set()
    unique_emails = [x for x in emails if not (x in seen or seen.add(x))]

    return unique_emails


def clean_contact_column(
    df: pd.DataFrame, contact_col: str = "contact"
) -> pd.DataFrame:
    """
    Clean contact column and create long format DataFrame with one email per row.

    Args:
        df: Input DataFrame
        contact_col: Name of the column containing contact information

    Returns:
        DataFrame in long format with one email per row
    """
    # Extract emails into lists
    df["email"] = df[contact_col].apply(extract_emails)

    # Explode the emails column to create one row per email
    df_long = df.explode("email").reset_index(drop=True)

    return df_long


def clean_email_column_no_dedupe(df, column_name="email"):
    """
    Cleans the specified email column in a DataFrame by:
    1. Stripping whitespace, converting to lowercase, and removing commas.
    2. Dropping rows where the email contains only a single letter or symbol.
    3. Dropping rows where the email is NaN.
    4. Valid email

    Args:
        df (pd.DataFrame): The DataFrame to clean.
        column_name (str): The column to process (default: "email").

    Returns:
        pd.DataFrame: Cleaned DataFrame (modification done safely).
    """
    df = df.copy()
    df[column_name] = (
        df[column_name]
        .str.strip()
        .str.lower()
        .str.replace(",", "", regex=True)
        .str.replace(" ", "")
    )
    df = df[~df[column_name].str.match(r"^[A-Za-z,_-]$", na=False)]
    df = df.dropna(subset=[column_name])

    # Fix e.g. "karanam@sansad.nic."
    df[column_name] = df[column_name].str.rstrip(".")
    # Fix e.g., 1.aron.praveen@gmail.com here but aron.praveen@gmail.com in scraped_pol_hibp.csv
    df[column_name] = df[column_name].str.lstrip("1.")
    df[column_name] = df[column_name].str.lstrip("2.")

    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

    df = df[df[column_name].str.match(email_regex, na=False)]

    return df


resolver = caching_resolver(timeout=10)


def clean_dedupe_email_column(df, column_name="email", dedup=True):
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
    df = df.copy()
    # ==============================================
    # Basic preprocessing
    # ==============================================
    df[column_name] = (
        df[column_name]
        .str.strip()
        .str.lower()
        .str.replace(",", "", regex=True)
        .str.replace(" ", "")
    )
    df = df[~df[column_name].str.match(r"^[A-Za-z,_-]$", na=False)]
    df = df.dropna(subset=[column_name])

    # Fix e.g. "karanam@sansad.nic."
    df[column_name] = df[column_name].str.rstrip(".")
    # Fix e.g., 1.aron.praveen@gmail.com here but aron.praveen@gmail.com in scraped_pol_hibp.csv
    df[column_name] = df[column_name].str.lstrip("1.")
    df[column_name] = df[column_name].str.lstrip("2.")

    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

    df = df[df[column_name].str.match(email_regex, na=False)]

    # ==============================================
    # Validate w/ PEV
    # ==============================================
    def validate_and_normalize(email):
        try:
            email_info = validate_email(
                email,
                check_deliverability=False,
            )
            return email_info.normalized.lower(), True
        except EmailNotValidError:
            return email, False

    df[["email", "valid_email"]] = df[column_name].apply(
        lambda x: pd.Series(validate_and_normalize(x))
    )

    df = df.query("valid_email==True")

    # ==============================================
    # Validate email domain existence and MX
    # ==============================================
    df["domain"] = df["email"].str.split("@").str[-1]

    df_edomain_validation = pd.read_csv(
        "../data/edomain_validation.csv", usecols=["domain", "valid_email_domain"]
    )
    df = df.merge(df_edomain_validation, on="domain", how="left", validate="m:1")

    df = df.query("valid_email_domain==True")

    # ==============================================
    df = df.drop(labels=["valid_email", "valid_email_domain", "domain"], axis=1)
    if dedup:
        df = df.drop_duplicates(subset=["email"], keep="first", ignore_index=True)

    return df


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
                all_names.update(
                    entry["Name"]
                    for entry in data
                    if isinstance(entry, dict) and "Name" in entry
                )
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

                present_names = {
                    entry["Name"]
                    for entry in data
                    if isinstance(entry, dict) and "Name" in entry
                }
            except (json.JSONDecodeError, TypeError):
                present_names = set()

        row = {"Filename": filename.replace(".json", "")}
        row.update({name: name in present_names for name in all_names})
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

    return df


def normalize_email(email):
    """Normalize the email string before extracting the domain."""
    try:
        normalized = validate_email(email, check_deliverability=False)
        return normalized.normalized.lower()  # Return the normalized email string
    except EmailNotValidError:
        print(f"Invalid: {email}")
        return email


def get_gov_patterns():
    """
    Returns core patterns that identify government email domains.
    Focuses on high-precision patterns that generalize across countries.
    """
    gov_dict = {
        # Core government domain patterns
        "Core TLD/Government Domains": [
            r"\.gov$",  # English pattern
            r"\.gov\.[a-z]{2,3}$",  # e.g., gov.uk, gov.sg
            r"\.gob$",  # Spanish pattern
            r"\.gouv$",  # French pattern
            r"\.go\.[a-z]{2,3}$",  # East Asian pattern
            r"\.gc\.[a-z]{2,3}$",  # Canada
            r"\.fed\.[a-z]{2,3}$",  # Federal (e.g., fed.us)
            r"\.mil$",  # Military
            r"\.admin$",  # Administrative (e.g., swiss admin.ch)
            r"\.bund$",  # German federal
            r"\.fgov$",  # Belgian federal
            r"\.nic\.",  # India (sansad.nic.in, etc.)
            r"\.mil\.za$",  # Department of Defence of SA
        ],

        # Known parliaments and ministries
        "Parliaments and Ministries": [
            r"ft\.dk$",  # Danish Parliament (Folketinget)
            r"senato\.it$",  # Italian Senate
            r"camera\.it$",  # Italy
            r"stortinget\.no$",  # Norwegian Parliament
            r"tweedekamer\.nl$",  # Netherlands
            r"cdep\.ro$",  # Romania
            r"eduskunta\.fi$",  # Finland
            r"assnat\.cm$",  # Cameroon
            r"riigikogu\.ee$",  # Estonia
            r"sobranie\.mk$",  # Macedonia
            r"dekamer\.be$",  # Belgium
            r"chd\.lu$",  # Luxembourg
            r"lachambre\.be$",  # Belgoum
            r"dna\.sr$",  # Suriname
            r"inatsisartut\.gl$",  # Greenland
            r"nanoq\.gl$",
            r"um\.dk$",  #
            r"fm\.dk$",  #
            r"skm\.dk$",  #
            r"sum\.dk$",  #
            r"trm\.dk$",  #
            r"uim\.dk$",  #
            r"jm\.dk$",  #
            r"kum\.dk$",  #
            r"bm\.dk$",  #
            r"uvm\.dk$",  #
            r"stm\.dk$",  #
            r"aeldremin\.dk$",  #
            r"fvm\.dk$",  #
            r"evm\.dk$",  #
            r"efkm\.dk$",  #
            r"km\.dk$",  #
            r"em\.dk$",  #
            r"oim\.dk$",  #
            r"sm\.dk$",  #
            r"ufm\.dk$",  #
            r"mfvm\.dk$",  #
            r"mssb\.dk$",  #
            r"mfa\.gr$",  # Greece
            r"istruzione\.it$",  # educ
            r"nic\.in$",  # India
            r"nrsr\.sk$",  # Slovakia
            r"nationalassembly\.sc$",  # Seychelles
            r"parliran\.ir$",  # Iran
            r"majles\.ir$",  # Iran
            r"europarl\.europa\.eu$",  # European Union
            r"giunta\.comune\.verona\.it$",  # City of Verona (Italy)
            r"comune\.pescara\.it$",         # City of Pescara (Italy)
            r"comune\.catania\.it$",         # City of Catania (Italy)
            r"regione\.liguria\.it$",        # Liguria regional government (Italy)
            r"regione\.lazio\.it$",          # Lazio regional government (Italy)
            r"provincia\.venezia\.it$",      # Venice provincial government (Italy)
            r"andorra\.ad$",                 # Andorra
            # broader patterns
            r"@.*\.gov(\.[a-z]{2,3})?$",  # Anchored email domain match
            r"@.*parliament\.",
            r"@.*senat\.",
            r"@.*assembly\.",
            r"@.*congress\.",
            r"@.*ministry\.",
            r"@.*cabinet\.",
            r"@.*bureau\.",
            r"\bparliament\b",
            r"\bparlament\b",
            r"\bparlamento\b",
            r"\bparl\b",
            r"\bsenat\b",
            r"\bsenado\b",
            r"\bassembly\b",  # assembly.wales,assemblee.pf,nationalassembly.sc,assembly.go.kr
            r"\bassemblee\b",  # assemblee.pf
            r"\basamblea\b",  # Nicaragua
            r"\bcongress\b",
            r"\bcongreso\b",  # congreso.gob.gt
            r"\bministry\b",
            r"\bcabinet\b",
            r"\bbureau\b",
            r"\bgovernment\b",
        ],

        # known political parties
        "Known Political Parties / Orgs": [
            r"dphk\.org$",  #
            r"bjpanda\.org$",
            r"iyc\.in$",
            r"da-mp\.org\.za$",
            r"ifp\.org\.za$",
            r"fondazionecraxi\.org$",  # Italy
            r"partitodemocratico\.it$",
            r"ecolo\.be$",
            r"liberal\.org\.hk$",  # HK
            r"dab\.org\.hk$",  # HK
            r"pap.org.sg$",  # Sg government
            r"prpg-grc\.sg$",  # Sg government
            r"wp\.sg$",  # sg
            r"udm\.org\.za$",
        ],
    }

    return (
        gov_dict["Core TLD/Government Domains"]
        + gov_dict["Parliaments and Ministries"]
        + gov_dict["Known Political Parties / Orgs"]
    )


def get_commercial_patterns() -> List[str]:
    """Get patterns for commercial domains."""
    return [
        r"\.com$",
        r"\.com\.",
        r"\.net$",
        r"\.net\.",
        r"\.co$",
        r"\.co\.",
        r"\.biz$",
        r"\.biz\.",
        r"\.info$",
        r"\.info\.",
        r"\.corp",
        r"libero\.it$",  # Italy
        r"\.ltd",
        r"\.inc",
        r"\.enterprise",
        r"\.business",
        r"yahoo",
        r"hotmail",
        r"gmail",
    ]


def classify_comm_gov_email(df: pd.DataFrame, email_col: str = "email") -> pd.DataFrame:
    """
    Prioritized classification of email domains.

    Classification rules:
      1. If matches government pattern -> Official
      2. If matches commercial pattern and not government -> Commercial
      3. Everything else -> Other
    """
    df = df.copy()

    # Extract domains from emails
    df["domain"] = df[email_col].str.split("@").str[1].str.lower()

    # Compile patterns
    gov_pattern = re.compile("|".join(get_gov_patterns()), re.IGNORECASE)
    commercial_pattern = re.compile("|".join(get_commercial_patterns()), re.IGNORECASE)

    # Create masks for pattern matching
    gov_mask = df["domain"].notna() & df["domain"].str.contains(gov_pattern, regex=True)
    commercial_mask = df["domain"].notna() & df["domain"].str.contains(
        commercial_pattern, regex=True
    )
    df = df.drop("domain", axis=1)

    # Initialize category column
    # df['ecategory'] = "Other"
    df["ecategory"] = "Commercial"

    # Apply classification rules in priority order
    df.loc[gov_mask, "ecategory"] = "Official"
    # df.loc[commercial_mask & ~gov_mask, 'ecategory'] = 'Commercial'

    return df


LIST_SERIOUS_DATACLASSES = [
    "Audio recordings",
    "Auth tokens",
    "Bank account numbers",
    "Biometric data",
    "Browsing histories",
    "Chat logs",
    "Credit card CVV",
    "Credit cards",
    "Credit status information",
    "Drinking habits",
    "Driver's licenses",
    "Drug habits",
    "Email messages",
    "Encrypted keys",
    "Government issued IDs",
    "Health insurance information",
    "Historical passwords",
    "HIV statuses",
    "Login histories",
    "MAC addresses",
    "Mothers maiden names",
    "Nationalities",
    "Partial credit card data",
    "Partial dates of birth",
    "Passport numbers",
    "Password hints",
    "Passwords",
    "Personal health data",
    "Photos",
    "PINs",
    "Places of birth",
    "Private messages",
    "Security questions and answers",
    "Sexual fetishes",
    "Sexual orientations",
    "SMS messages",
    "Social security numbers",
    "Taxation records",
]


# Not found in hibp payloads
DELINQUENTS = [
    "m.chrysomallis@parliament.gr",
    "r.christidou@parliament.gr",
    "3@abc.com",
    "3@gmail.com",
    "dhanwatichandela498@gmail.com",
    "_bsec@pap.org.sg",
    "mariamjaafar@gmail.com",
]
