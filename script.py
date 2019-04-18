import os
import requests
from dotenv import load_dotenv
import statistics
import terminaltables


SUPERJOB_CATALOGUE = 48


class TownNotFound(BaseException):
    pass


def get_predict_salary(salary_from, salary_to):
    if salary_from in (None, 0) and salary_to in (None, 0):
        return None

    if salary_from in (None, 0):
        return salary_to * 0.8

    if salary_to in (None, 0):
        return salary_from * 1.2

    return (salary_to - salary_from) / 2


def find_hh_area_recursive(areas, text):
    for area in areas:
        if area['name'] == text:
            return area['id']
        if area['areas']:
            area_id = find_hh_area_recursive(area['areas'], text)
            if area_id is not None:
                return area_id


def get_hh_area_id(text):
    url = "https://api.hh.ru/areas"
    response = requests.get(url)
    response.raise_for_status()
    area_id = find_hh_area_recursive(response.json(), text)
    if not area_id:
        raise TownNotFound('Город HeadHunter не найден')
    return area_id


def get_hh_vacancies(text, area_id=None, period=None):
    vacancies = []
    url = "https://api.hh.ru/vacancies"
    params = {'text': text,
              'per_page': 20,
              'page': 0,
              'area': area_id,
              'period': period}

    while True:
        response = requests.get(url, params=params)
        response.raise_for_status()
        pages = response.json()['pages']
        vacancies += response.json()['items']
        params['page'] += 1
        if params['page'] >= pages:
            break

    return vacancies


def predict_rub_salary_hh(vacancy):
    if vacancy['salary'] is None or vacancy['salary']['currency'] != 'RUR':
        return None

    return get_predict_salary(vacancy['salary']['from'], vacancy['salary']['to'])


def get_salaries(vacancies, func):
    salaries = []
    for vacancy in vacancies:
        salary = func(vacancy)
        if salary is not None:
            salaries.append(salary)
    return salaries


def predict_hh_programmers_vacancies(languages, area=None, period=None):
    vacancies = {}
    area_id = get_hh_area_id(area) if area is not None else None

    for language in languages:
        vacancies_found = get_hh_vacancies(f'программист {language}', area_id, period)
        salaries = list(filter(lambda x: x is not None, (predict_rub_salary_hh(v) for v in vacancies_found)))
        vacancies[language] = {"vacancies_found": len(vacancies_found),
                               "vacancies_processed": len(salaries),
                               "average_salary": int(statistics.mean(salaries))}

    return vacancies


def get_sj_area_id(keyword):
    url = "https://api.superjob.ru/2.0/towns/"
    params = {'keyword': keyword, 'all': True}
    response = requests.get(url, params=params)
    response.raise_for_status()
    if len(response.json()['objects']) < 1:
        raise TownNotFound('Город SuperJob не найден')
    return response.json()['objects'][0]['id']


def get_sj_vacancies(key, keyword, area_id=None, catalogues=None):
    url = "https://api.superjob.ru/2.0/vacancies/"
    headers = {'X-Api-App-Id': key}
    params = {'keyword': keyword, 'catalogues': catalogues, 'page': 0, 'count': 100}
    if area_id is not None:
        params['town'] = area_id

    vacancies = []
    while True:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        pages = response.json()['total'] // 100 + 1
        vacancies += response.json()['objects']
        params['page'] += 1
        if params['page'] >= pages:
            break
    return vacancies


def predict_rub_salary_sj(vacancy):
    if vacancy['currency'] != 'rub':
        return None

    return get_predict_salary(vacancy['payment_from'], vacancy['payment_to'])


def predict_sj_programmers_vacancies(key, languages, area=None, catalogue=None):
    vacancies = {}
    area_id = get_sj_area_id(area) if area is not None else None

    for language in languages:
        vacancies_found = get_sj_vacancies(key, f'программист {language}', area_id, catalogue)
        salaries = list(filter(lambda x: x is not None, (predict_rub_salary_sj(v) for v in vacancies_found)))
        vacancies[language] = {"vacancies_found": len(vacancies_found),
                               "vacancies_processed": len(salaries),
                               "average_salary": int(statistics.mean(salaries))}

    return vacancies


def print_table(vacancies, title):
    table_data = [
        ('Язык программирования', 'Найдено вакансий', 'Обработано вакансий', 'Средняя зарплата, руб.')
    ]
    for language, stat in vacancies.items():
        table_data.append([language,
                           stat['vacancies_found'],
                           stat['vacancies_processed'],
                           stat['average_salary']])
    table = terminaltables.AsciiTable(table_data, title)
    print(table.table)


def main():
    load_dotenv()
    languages = ['Java', 'Python', 'PHP', 'C++', 'C#', 'GO', 'JS']
    try:
        vacancies = predict_hh_programmers_vacancies(languages, 'Москва', 30)
        print_table(vacancies, 'HeadHunter Moscow')

        superjob_key = os.getenv('SUPERJOB_KEY', False)
        if superjob_key:
            vacancies = predict_sj_programmers_vacancies(superjob_key, languages, 'Москва', SUPERJOB_CATALOGUE)
            print_table(vacancies, 'SuperJob Moscow')
    except TownNotFound as e:
        print(f'Error: {e}')


if __name__ == '__main__':
    main()
