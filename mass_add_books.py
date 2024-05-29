import aiohttp
import argparse
import asyncio
import re
import sys
import pandas as pd


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='Calibre-Web Mass Book Adder',
        description='A utility tool to bulk add books to shelves in Calibre-Web',
    )

    parser.add_argument(
        '--username',
        type=str,
        help='The username of the Calibre-Web server',
        default='admin',
    )
    parser.add_argument(
        '--password',
        type=str,
        help='The password of the Calibre-Web server',
        default='admin123',
    )
    parser.add_argument(
        '--address',
        type=str,
        help='The address of the Calibre-Web server',
        default='http://127.0.0.1:8083',
    )
    parser.add_argument(
        '--shelf_id',
        type=str,
        help='The ID of the shelf to add the books to',
        default='1',
    )
    parser.add_argument(
        '--booklist',
        type=str,
        help='The path to the CSV file containing the list of books to add',
        default='Meine Bücher.csv',
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        help='The number of concurrent requests to make',
        default=20,
    )

    return parser.parse_args()


async def login(session: aiohttp.ClientSession,
                address: str,
                username: str,
                password: str,
                ) -> str:
    try:
        login_page = await session.get(address + '/login')
        page_content = await login_page.text()
        token = re.search('<input type="hidden" name="csrf_token" value="(.*)">', page_content)
        login_response = await session.post(
            address + '/login?next=/',
            data={
                'username': username,
                'password': password,
                'submit': '',
                'remember_me': 'on',
                'next': '/',
                "csrf_token": token.group(1),
            },
        )
        if "login" in login_response.text or login_response.status != 200:
            print('Error: Could not log in to calibre-web')
            sys.exit(1)

        return token.group(1)
    except Exception as e:
        print(f"Error connecting to calibre-web : {e}")
        sys.exit(1)


async def add_book_to_shelf(session: aiohttp.ClientSession,
                            sem: asyncio.Semaphore,
                            token: str,
                            address: str,
                            shelf_id: str,
                            book_id: str,
                            ):
    async with sem:
        try:
            payload = {"csrf_token": token}
            headers = {'Referer': address + '/'}
            post_response = await session.post(address + '/shelf/add/' + shelf_id + '/' + book_id,
                                               data=payload,
                                               headers=headers)

            if post_response.status == 200:
                message = re.findall(u"id=\"flash_.*class=.*>(.*)</div>", await post_response.text())
                if not message:
                    print(f'Error: Book with id {book_id} already in shelf, or shelf not existing')
                else:
                    print(
                        f'Request to add Book with id {book_id} to shelf was successfully send. Calibre-Web Response: {message[0]}')
            else:
                print(f'Error: Failed to add book with id {book_id} to shelf {shelf_id}')
        except Exception as e:
            print(f"Error adding book with id {book_id} to shelf: {e}")


async def main():
    args = parse_arguments()
    sem = asyncio.Semaphore(args.concurrency)

    async with aiohttp.ClientSession() as session:
        # Login to Calibre-Web and get the CSRF token
        token = await login(session, args.address, args.username, args.password)

        # Read the book ids into a pandas dataframe
        try:
            df = pd.read_csv(args.booklist)
        except Exception as e:
            print(f"Error on opening books list file: {e}")
            sys.exit(1)

        # Add the books to the shelf
        for index, row in df.iterrows():
            book_id = row.get('id', row.get("\ufeffid"))
            if book_id.isdigit():
                await add_book_to_shelf(
                    session=session,
                    sem=sem,
                    token=token,
                    address=args.address,
                    shelf_id=args.shelf_id,
                    book_id=book_id,
                )
            else:
                print(f'Error: id {book_id} is not a number')


if __name__ == '__main__':
    asyncio.run(main())
