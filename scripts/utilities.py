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
    df[column_name] = df[column_name].str.strip().str.lower().str.replace(",", "", regex=True).str.replace(" ", "")
    df = df[~df[column_name].str.match(r"^[A-Za-z,_-]$", na=False)]
    df = df.dropna(subset=[column_name])

    # Fix e.g. "karanam@sansad.nic."
    df[column_name] = df[column_name].str.rstrip(".")
    # Fix e.g., 1.aron.praveen@gmail.com here but aron.praveen@gmail.com in scraped_pol_hibp.csv
    df[column_name] = df[column_name].str.lstrip("1.")
    df[column_name] = df[column_name].str.lstrip("2.")
    
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

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
                email, check_deliverability=False,
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

    df_edomain_validation = pd.read_csv("../data/edomain_validation.csv", usecols=["domain", "valid_email_domain"])
    df = df.merge(df_edomain_validation, on="domain", how="left", validate="m:1")
    
    df = df.query("valid_email_domain==True")
    
    # ==============================================
    df = df.drop(labels=["valid_email", "valid_email_domain"], axis=1)
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



def get_gov_patterns() -> Dict[str, List[str]]:
    """Get comprehensive patterns for government domains."""
    return {
        # Standard government patterns
        "General": [r'\.gov\.',  r'\.gov$', r'\.gob\.', r'\.gouv\.', r'\.go\.'],
        
        # Regional government patterns
        "Europe": [
            r'\.admin\.ch$', r'\.gouv\.fr$', r'\.bund\.de$', r'\.regering\.nl$',
            r'\.regeringen\.se$', r'\.regjeringen\.no$', r'\.fgov\.be$'
        ],
        
        # Asia Pacific
        "Asia": [
            r'\.go\.jp$', r'\.go\.kr$', r'\.go\.id$', r'\.gov\.cn$', r'\.政务\.cn$',
            r'\.gov\.in$', r'\.nic\.in$', r'\.gov\.sg$', r'\.go\.th$'
        ],
        
        # Americas
        "Americas": [
            r'\.gc\.ca$', r'\.canada\.ca$', r'\.gob\.mx$', r'\.gob\.ar$',
            r'\.gob\.cl$', r'\.gob\.pe$', r'\.gob\.ec$'
        ],
        
        # Official institutions
        "Institutions": [
            r'parliament', r'parl', r'assembly', r'senate', r'house',
            r'legislature', r'congress', r'cabinet', r'ministry'
        ],
        
        # Education and Research
        "Education": [
            r'\.edu\.', r'\.edu$', r'\.ac\.', r'\.ac$',
            r'\.edu\.gov', r'\.research\.gov'
        ],
        
        # Military and Defense
        "Military": [
            r'\.mil$', r'\.mil\.', r'\.defense\.gov', r'\.mod\.',
            r'\.defence\.gov'
        ]
    }

def get_commercial_patterns() -> List[str]:
    """Get patterns for commercial domains."""
    return [
        r'\.com$', r'\.com\.', 
        r'\.net$', r'\.net\.',
        r'\.co$', r'\.co\.',
        r'\.biz$', r'\.biz\.',
        r'\.info$', r'\.info\.',
        r'\.corp', r'\.ltd', r'\.inc',
        r'\.enterprise', r'\.business'
    ]

def classify_comm_gov_email(df: pd.DataFrame, 
                          email_col: str = "email",
                          default_category: str = "Official") -> pd.DataFrame:
    """
    Enhanced classification of email domains as Commercial or Official.
    
    Classification rules:
    1. Extracts domain from email address
    2. Checks against comprehensive list of government patterns
    3. Checks against commercial patterns
    4. Uses contextual clues from domain name
    
    Args:
        df: DataFrame containing email column
        email_col: Name of email column
        default_category: Default category if classification is uncertain
        
    Returns:
        DataFrame with added 'domain' and 'ecategory' columns
    """
    df = df.copy()
    
    # Extract domain
    df['domain'] = df[email_col].str.split('@').str[1]
    
    # Compile all government patterns
    gov_patterns = get_gov_patterns()
    all_gov_patterns = []
    for patterns in gov_patterns.values():
        all_gov_patterns.extend(patterns)
    official_pattern = re.compile('|'.join(all_gov_patterns), re.IGNORECASE)
    
    # Compile commercial patterns
    commercial_pattern = re.compile('|'.join(get_commercial_patterns()), re.IGNORECASE)
    
    def _classify_domain(domain: str) -> str:
        """Classify a single domain."""
        if pd.isna(domain):
            return default_category
            
        domain = domain.lower()
        
        # Check official patterns first
        if official_pattern.search(domain):
            return 'Official'
            
        # Then check commercial patterns
        if commercial_pattern.search(domain):
            return 'Commercial'
            
        # Additional checks for government-related keywords
        gov_keywords = {
            'government', 'ministry', 'minister', 'dept', 'department',
            'agency', 'bureau', 'commission', 'authority', 'council',
            'committee', 'secretariat', 'directorate', 'office'
        }
        
        domain_parts = set(re.split(r'[.-]', domain))
        if domain_parts & gov_keywords:  # If there's any intersection
            return 'Official'
            
        return default_category
    
    # Apply classification
    df['ecategory'] = df['domain'].apply(_classify_domain)
    
    # Add confidence level based on pattern matching
    def _get_confidence(row):
        if pd.isna(row['domain']):
            return 'low'
        domain = row['domain'].lower()
        category = row['ecategory']
        
        if category == 'Official':
            if official_pattern.search(domain):
                return 'high'
            return 'medium'
        else:  # Commercial
            if commercial_pattern.search(domain):
                return 'high'
            return 'medium'
    
    df['confidence'] = df.apply(_get_confidence, axis=1)
    
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
