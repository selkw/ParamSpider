import time
import requests
import argparse
import os
import logging
import colorama
from colorama import Fore, Style
from . import client
from urllib.parse import urlparse, parse_qs, urlencode

# Inisialisasi kode warna untuk output terminal
yellow_color_code = "\033[93m"
reset_color_code = "\033[0m"

# Inisialisasi colorama untuk output terminal berwarna
colorama.init(autoreset=True)

# Format log pesan
log_format = '%(message)s'
logging.basicConfig(format=log_format, level=logging.INFO)
logging.getLogger('').handlers[0].setFormatter(logging.Formatter(log_format))

# Daftar ekstensi file yang ingin diambil dari Wayback Machine
HARDCODED_EXTENSIONS = [
    ".jpg", ".jpeg", ".png", ".gif", ".pdf", ".svg", ".json",
    ".css", ".js", ".webp", ".woff", ".woff2", ".eot", ".ttf", ".otf", ".mp4", ".txt"
]

def has_extension(url, extensions):
    """
    Memeriksa apakah URL memiliki ekstensi file yang sesuai dengan daftar ekstensi yang diberikan.

    Args:
        url (str): URL yang akan diperiksa.
        extensions (list): Daftar ekstensi file yang ingin diperiksa.

    Returns:
        bool: True jika URL memiliki ekstensi yang sesuai, False jika tidak.
    """
    parsed_url = urlparse(url)
    path = parsed_url.path
    extension = os.path.splitext(path)[1].lower()

    return extension in extensions

def clean_url(url):
    """
    Membersihkan URL dengan menghapus informasi port yang redundan untuk URL HTTP dan HTTPS.

    Args:
        url (str): URL yang akan dibersihkan.

    Returns:
        str: URL yang telah dibersihkan.
    """
    parsed_url = urlparse(url)

    if (parsed_url.port == 80 and parsed_url.scheme == "http") or (parsed_url.port == 443 and parsed_url.scheme == "https"):
        parsed_url = parsed_url._replace(netloc=parsed_url.netloc.rsplit(":", 1)[0])

    return parsed_url.geturl()

def clean_urls(urls, extensions, placeholder):
    """
    Membersihkan daftar URL dengan menghapus parameter dan string query yang tidak perlu.

    Args:
        urls (list): Daftar URL yang akan dibersihkan.
        extensions (list): Daftar ekstensi file yang ingin diperiksa.

    Returns:
        list: Daftar URL yang telah dibersihkan.
    """
    cleaned_urls = set()
    for url in urls:
        cleaned_url = clean_url(url)
        if not has_extension(cleaned_url, extensions):
            parsed_url = urlparse(cleaned_url)
            query_params = parse_qs(parsed_url.query)
            cleaned_params = {key: placeholder for key in query_params}
            cleaned_query = urlencode(cleaned_params, doseq=True)
            cleaned_url = parsed_url._replace(query=cleaned_query).geturl()
            cleaned_urls.add(cleaned_url)
    return list(cleaned_urls)

def fetch_and_clean_urls(domain, extensions, stream_output, proxy, placeholder, output_path):
    """
    Mengambil dan membersihkan URL terkait domain tertentu dari Wayback Machine.

    Args:
        domain (str): Nama domain untuk mengambil URL terkait.
        extensions (list): Daftar ekstensi file yang ingin diperiksa.
        stream_output (bool): True jika ingin streaming URL ke terminal.
        output_path (str): Path untuk menyimpan URL yang telah dibersihkan.

    Returns:
        None
    """
    logging.info(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Mengambil URLs untuk {Fore.CYAN + domain + Style.RESET_ALL}")

    # Hapus http:// atau https:// dari domain jika ada
    domain = domain.replace("http://", "").replace("https://", "")

    # Buat URI untuk melakukan pencarian URL pada Wayback Machine
    wayback_uri = f"https://web.archive.org/cdx/search/cdx?url={domain}/*&output=txt&collapse=urlkey&fl=original&page=/"

    # Inisialisasi variabel untuk percobaan pengambilan
    max_retries = 3
    retry_delay = 5  # Detik
    for attempt in range(max_retries):
        try:
            # Mengambil konten dari URL Wayback Machine dengan menggunakan client.fetch_url_content
            response = client.fetch_url_content(wayback_uri, proxy)

            # Jika responsenya sukses (status code 200), lanjutkan
            if response.status_code == 200:
                break
        except requests.RequestException as e:
            # Tangani kesalahan jika ada, dan coba lagi setelah beberapa detik
            logging.error(f"Error fetching URL {wayback_uri}. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)
    else:
        # Jika setelah beberapa percobaan tetap gagal, log kesalahan
        logging.error(f"Gagal mengambil URL {wayback_uri} setelah {max_retries} percobaan.")
        return

    # Memisahkan respons teks menjadi daftar URL
    urls = response.text.split()

    logging.info(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Ditemukan {Fore.GREEN + str(len(urls)) + Style.RESET_ALL} URLs untuk {Fore.CYAN + domain + Style.RESET_ALL}")

    # Membersihkan daftar URL dari parameter yang tidak perlu
    cleaned_urls = clean_urls(urls, extensions, placeholder)
    logging.info(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Membersihkan URLs untuk {Fore.CYAN + domain + Style.RESET_ALL}")
    logging.info(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Ditemukan {Fore.GREEN + str(len(cleaned_urls)) + Style.RESET_ALL} URLs setelah membersihkan")
    logging.info(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Mengekstrak URLs dengan parameter")

    # Menyimpan hasil ke file teks di folder home user jika output_path tidak diberikan
    home_dir = os.path.expanduser("~")
    base_result_file = os.path.join(home_dir, f"param.txt")

    if output_path:
        if os.path.exists(output_path):
            raise FileExistsError(f"Berkas output '{output_path}' sudah ada. Silakan tentukan nama yang berbeda.")
        base_result_file = output_path

    result_file = base_result_file
    counter = 1

    # Tambahkan nomor urut jika nama file yang sama sudah ada dan output_path tidak diberikan
    while not output_path and os.path.exists(result_file):
        result_file = f"{os.path.splitext(base_result_file)[0]}_{counter}.txt"
        counter += 1

    # Menyimpan cleaned_urls ke dalam file teks
    with open(result_file, "w") as f:
        for url in cleaned_urls:
            if "?" in url:  # Hanya menyimpan URL yang memiliki parameter
                f.write(url + "\n")
                if stream_output:
                    print(url)

    # Log pesan bahwa URLs telah disimpan
    logging.info(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} URLs yang telah dibersihkan disimpan di {Fore.CYAN + result_file + Style.RESET_ALL}")

def main():
    """
    Fungsi utama untuk menangani argumen baris perintah dan memulai proses penambangan URL.
    """
    log_text = """
                                      _    __
   ___  ___ ________ ___ _  ___ ___  (_)__/ /__ ____
  / _ \/ _ `/ __/ _ `/  ' \(_-</ _ \/ / _  / -_) __/
 / .__/\_,_/_/  \_,_/_/_/_/___/ .__/_/\_,_/\__/_/
/_/                          /_/

                              with <3 by @0xasm0d3us
    """
    colored_log_text = f"{yellow_color_code}{log_text}{reset_color_code}"
    print(colored_log_text)
    parser = argparse.ArgumentParser(description="Mining URLs from dark corners of Web Archives")
    parser.add_argument("-d", "--domain", help="Domain name to fetch related URLs for.")
    parser.add_argument("-l", "--list", help="File containing a list of domain names.")
    parser.add_argument("-s", "--stream", action="store_true", help="Stream URLs on the terminal.")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--proxy", help="Set the proxy address for web requests.", default=None)
    parser.add_argument("-p", "--placeholder", help="Placeholder for parameter values", default="FUZZ")
    args = parser.parse_args()

    if not args.domain and not args.list:
        parser.error("Please provide either the -d option or the -l option.")

    if args.domain and args.list:
        parser.error("Please provide either the -d option or the -l option, not both.")

    if args.list:
        with open(args.list, "r") as f:
            domains = [line.strip().lower().replace('https://', '').replace('http://', '') for line in f.readlines()]
            domains = [domain for domain in domains if domain]  # Remove empty lines
            domains = list(set(domains))  # Remove duplicates
    else:
        domain = args.domain

    extensions = HARDCODED_EXTENSIONS

    if args.domain:
        fetch_and_clean_urls(domain, extensions, args.stream, args.proxy, args.placeholder, args.output)

    if args.list:
        for domain in domains:
            fetch_and_clean_urls(domain, extensions, args.stream, args.proxy, args.placeholder, args.output)

if __name__ == "__main__":
    main()
