#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import argparse
import csv
import os
import subprocess
from datetime import datetime

# Torch - Dependencias
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Proxy para Tor
proxies = {
    'http': 'socks5h://127.0.0.1:9050',
    'https': 'socks5h://127.0.0.1:9050'
}

# Engines ativas
ENGINES = {
    "ahmia": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={}",
    "haystack": "http://haystak5njsmn2hqkewecpaxetahtwhsbsa64jom2k22z5afxhnpxfid.onion/?q={}",
    "VormWeb": "https://vormweb.de/en/search?q={}",
    "torch": None
}

def search_torch(query, limit=None, debug=False):
    """Realizar busca no Torch usando Selenium, com proxy configurado diretamente."""
    base_url = "http://xmh57jrknzkhv6y3ls3ubitzfqnkrwxhopf5aygthi7d6rplyvk3noyd.onion/cgi-bin/omega/omega"

    exclude_patterns = ["/", "/adinfo.html"]

    # Configuração do Selenium com perfil do Tor
    options = Options()
    options.set_preference("network.proxy.type", 1)
    options.set_preference("network.proxy.socks", "127.0.0.1")
    options.set_preference("network.proxy.socks_port", 9050)
    options.set_preference("network.proxy.socks_remote_dns", True)
    options.add_argument("--headless")  # Executar sem interface gráfica

    geckodriver_path = "/usr/local/bin/geckodriver"
    service = Service(geckodriver_path)

    driver = webdriver.Firefox(service=service, options=options)
    results = []

    try:
        if debug:
            print("[DEBUG] Acessando a página inicial do Torch...")
        driver.get(base_url)

        # Garantir que o campo de busca esteja disponível
        if debug:
            print("[DEBUG] Localizando o campo de busca...")
        search_box = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='P']"))
        )

        # Inserir a pesquisa e submeter o formulário
        search_box.send_keys(query)
        if debug:
            print(f"[DEBUG] Pesquisa inserida: {query}")

        submit_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit']"))
        )
        submit_button.click()
        if debug:
            print("[DEBUG] Pesquisa enviada.")

        # Processar as páginas de resultados
        while True:
            if debug:
                print("[DEBUG] Coletando resultados da página...")
            WebDriverWait(driver, 60).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href]"))
            )

            html_content = driver.page_source
            soup = BeautifulSoup(html_content, "html.parser")
            items = soup.find_all("a", href=True)
            if debug:
                print(f"[DEBUG] Total de links encontrados na página: {len(items)}")
            for item in items:
                link = item.get('href')
                if any(link.endswith(pattern) or link == pattern for pattern in exclude_patterns):
                    if debug:
                        print(f"[DEBUG] Link excluído: {item["href"]}")
                else:
                    title = item.text.strip() if item.text else "Sem título"
                    url = item["href"]
                    if debug:
                        print(f"[DEBUG] Link: {url}, Título: {title}")
                    results.append({"engine": "Torch", "title": title, "url": url})

            if limit and len(results) >= limit:
                print(f"[INFO] Limite de {limit} resultados atingido. - Torch")
                break

            # Verificar se há um link para a próxima página
            try:
                next_page = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][name='>'][value='Next']")
                if debug:
                    print("[DEBUG] Indo para a próxima página...")
                next_page.click()
                WebDriverWait(driver, 60).until(
                    EC.staleness_of(next_page)
                )  # Esperar que a página carregue
            except Exception as e:
                if debug:
                    print("[DEBUG] Nenhuma próxima página encontrada. Finalizando.")
                break

        return results
    except Exception as e:
        print(f"[ERRO] Torch: {e}")
        return []
    finally:
        driver.quit()



ENGINES["torch"] = search_torch


def search_engine(engine_name, query, limit=None, debug=False):
    """Realizar busca em uma engine específica com ajustes para links relativos."""
    if engine_name == "torch":
        return search_torch(query, limit, debug)
    base_url = ENGINES[engine_name].format(query)
    results = []
    results_set = set()

    match engine_name:
        case "ahmia":
            exclude_patterns = [
                "/about/", "/add/", "/legal/", "/", "#", "/blacklist/", "&d=all", "&d=1", "&d=7", "&d=30"
            ]
        case _:
            exclude_patterns = []
            if debug:
                print(f"[DEBUG] Nenhum caminho excluido de {engine_name}")

    try:
        response = requests.get(base_url, proxies=proxies, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Coletar links
        items = soup.find_all('a', href=True)
        for item in items:
            link = item.get('href')
            if link:
                # Completar links relativos
                if not link.startswith("http"):
                    link = base_url + link

                if debug:
                    print(f"[DEBUG] Link encontrado: {link}")

                # Verificar exclusões
                if any(link.endswith(pattern) or link == pattern for pattern in exclude_patterns):
                    if debug:
                        print(f"[DEBUG] Link excluído: {link}")
                    continue

                # Adicionar ao resultado se ainda não estiver na lista
                if link not in results_set:
                    results_set.add(link)
                    result = {
                        "engine": engine_name,
                        "title": item.text.strip() if item.text else "Sem título",
                        "url": link,
                        "description": item.get('title', "Sem descrição")
                    }
                    results.append(result)
                    if debug:
                        print(f"[DEBUG] Resultado adicionado: {result}")

                    # Verificar limite
                    if limit and len(results) >= limit:
                        if debug:
                            print(f"[INFO] Limite atingido: {limit}")
                        break
    except requests.exceptions.RequestException as e:
        print(f"[ERRO] {engine_name}: {e}")

    if debug:
        print(f"[DEBUG] Final de execução - Total de resultados coletados para {engine_name}: {len(results)}")
    return results

def save_to_csv(results, output_file):
    """Salvar os resultados em um arquivo CSV."""
    fields = ["engine", "title", "url", "description"]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

def open_in_default_application(file_path):
    """Abrir o arquivo no aplicativo padrão de planilhas."""
    print("Abrindo resultado...")
    if os.name == "nt":  # Windows
        os.startfile(file_path)
    elif os.name == "posix":  # Linux/macOS
        subprocess.Popen(["xdg-open", file_path], start_new_session=True)
    else:
        print(f"[INFO] Abra manualmente o arquivo: {file_path}")

def main():
    # Configuração dos argumentos
    parser = argparse.ArgumentParser(description="Buscador de páginas na dark web.")
    parser.add_argument("--query", required=True, help="Palavra-chave para buscar.")
    parser.add_argument("--limit", type=int, default=None, help="Limite de resultados por engine.")
    parser.add_argument("--engines", nargs="+", choices=ENGINES.keys(), default=list(ENGINES.keys()), help="Engines para usar na busca.")
    parser.add_argument("--output", help="Arquivo para salvar os resultados.")
    parser.add_argument("--debug", action="store_true", help="Exibir informações de depuração.")
    args = parser.parse_args()

    # Feedback inicial
    print(f"Iniciando busca por '{args.query}'...")
    all_results = []

    # Barra de progresso
    with tqdm(total=len(args.engines), desc="Progresso das engines") as pbar:
        for engine in args.engines:
            print(f"\nBuscando na engine: {engine}")
            results = search_engine(engine, args.query, args.limit, debug=args.debug)
            if results:
                print(f"[INFO] {len(results)} resultados encontrados em {engine}.")
                all_results.extend(results)
            else:
                print(f"[INFO] Nenhum resultado encontrado em {engine}.")
            pbar.update(1)

    # Salvar resultados
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"dwbusca_{timestamp}_{args.query.replace(' ', '_')}.csv"
    
    if all_results:
        save_to_csv(all_results, args.output)
        print(f"\n[INFO] Resultados salvos em: {args.output}")
        open_in_default_application(args.output)
    else:
        print("\n[INFO] Nenhum resultado encontrado em nenhuma engine.")

if __name__ == "__main__":
    main()


