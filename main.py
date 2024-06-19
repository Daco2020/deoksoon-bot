import os
import csv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from datetime import datetime
from slack_sdk import WebClient

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.command("/문장제출")
def handle_submit_command(ack, body, client):
    ack()

    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "submit_view",
            "private_metadata": body["channel_id"],
            "title": {"type": "plain_text", "text": "제출하기"},
            "submit": {"type": "plain_text", "text": "제출"},
            "close": {"type": "plain_text", "text": "취소"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "title_block_id",
                    "label": {
                        "type": "plain_text",
                        "text": "책 제목",
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "input_action_id",
                        "multiline": False,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "책 제목을 입력해주세요.",
                        },
                    },
                },
                {
                    "type": "input",
                    "block_id": "sentence_block_id",
                    "label": {
                        "type": "plain_text",
                        "text": "오늘의 문장",
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "input_action_id",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "기억에 남는 문장을 입력해주세요.",
                        },
                    },
                },
                {
                    "type": "input",
                    "block_id": "comment_block_id",
                    "label": {
                        "type": "plain_text",
                        "text": "생각 남기기",
                    },
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "input_action_id",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "생각을 자유롭게 남겨주세요.",
                        },
                    },
                },
            ],
        },
    )


@app.view("submit_view")
def handle_view_submission_events(ack, body, client):

    # 입력값에 대한 유효성 검사
    channel_id = body["view"]["private_metadata"]
    if channel_id != "C073SJEJ4GL":
        ack(
            response_action="errors",
            errors={"sentence_block_id": "#오늘의 문장 채널에서만 제출할 수 있습니다."},
        )
        return None

    sentence = body["view"]["state"]["values"]["sentence_block_id"]["input_action_id"][
        "value"
    ]
    if len(sentence) < 3:
        ack(
            response_action="errors",
            errors={"sentence_block_id": "오늘의 문장은 세 글자 이상 입력해주세요."},
        )
        return None

    ack()

    # 저장할 데이터 추출
    user_id = body["user"]["id"]
    user_info = client.users_info(user=user_id)
    user_name = user_info["user"]["real_name"]
    book_title = body["view"]["state"]["values"]["title_block_id"]["input_action_id"][
        "value"
    ]
    comment = body["view"]["state"]["values"]["comment_block_id"]["input_action_id"][
        "value"
    ]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # data 디렉토리가 없다면 생성
    if not os.path.exists("data"):
        os.makedirs("data")

    # 제출 정보를 CSV 파일에 저장
    with open("data/contents.csv", "a", newline="") as csvfile:
        writer = csv.writer(csvfile)

        if not os.path.getsize("data/contents.csv") > 0:
            writer.writerow(
                [
                    "user_id",
                    "user_name",
                    "book_title",
                    "sentence",
                    "comment",
                    "created_at",
                ]
            )
        writer.writerow(
            [
                user_id,
                user_name,
                book_title,
                sentence,
                comment,
                created_at,
            ]
        )

    # 완료메시지 가공 및 슬랙으로 전송
    text = f">>> *<@{user_id}>님이 `{book_title}` 에서 뽑은 오늘의 문장*\n\n '{sentence}'\n"
    if comment:
        text += f"\n {comment}\n"

    client.chat_postMessage(channel=channel_id, text=text)


@app.command("/제출내역")
def handle_submission_history_command(ack, body, client: WebClient):
    ack()
    user_id = body["user_id"]

    # 사용자의 DM 채널 ID 가져오기
    response = client.conversations_open(users=user_id)
    dm_channel_id = response["channel"]["id"]

    # 만약에 제출내역 파일이 없다면 제출내역이 없다고 메시지를 전송하고 종료
    if not os.path.exists("data/contents.csv"):
        client.chat_postMessage(channel=dm_channel_id, text="제출내역이 없습니다.")
        return None

    # 사용자의 제출내역만 필터링
    submission_list = []

    with open("data/contents.csv") as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames
        for row in reader:
            if row["user_id"] == user_id:
                submission_list.append(row)

    # 만약에 제출내역이 없다면 제출내역이 없다고 메시지를 전송하고 종료
    if not submission_list:
        client.chat_postMessage(channel=dm_channel_id, text="제출내역이 없습니다.")
        return None

    # 사용자의 제출내역을 CSV 파일로 임시 저장 후 전송
    temp_dir = "data/temp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    temp_file_path = f"{temp_dir}/{user_id}.csv"
    with open(temp_file_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames)
        writer.writeheader()
        writer.writerows(submission_list)

    client.files_upload_v2(
        channel=dm_channel_id,
        file=temp_file_path,
        initial_comment=f"<@{user_id}> 님의 제출내역 입니다!",
    )

    # 임시로 생성한 CSV 파일을 삭제
    os.remove(temp_file_path)


@app.command("/관리자")
def handle_admin_command(ack, body, client: WebClient):
    ack()

    # 관리자인지 확인 후 아니라면 메시지 전송 후 종료
    user_id = body["user_id"]
    if user_id != "U073M3MVA13":
        client.chat_postEphemeral(
            channel=body["channel_id"],
            user=user_id,
            text="관리자만 사용 가능한 명령어입니다.",
        )
        return None

    # 관리자용 버튼 전송(전체 제출내역을 반환)
    client.chat_postEphemeral(
        channel=body["channel_id"],
        user=user_id,
        text="관리자 메뉴를 선택해주세요.",
        blocks=[
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "전체 제출내역 조회",
                            "emoji": True,
                        },
                        "value": "admin_value_1",
                        "action_id": "fetch_all_submissions",
                    }
                ],
            }
        ],
    )


@app.action("fetch_all_submissions")
def handle_some_action(ack, body, client: WebClient):
    ack()
    # 관리자의 DM 채널 ID 가져오기
    response = client.conversations_open(users=body["user"]["id"])
    dm_channel_id = response["channel"]["id"]

    # 전체 제출내역을 불러와서 전송
    file_path = "data/contents.csv"
    if not os.path.exists(file_path):
        client.chat_postMessage(
            channel=dm_channel_id,
            text="제출내역이 없습니다.",
        )
        return None

    client.files_upload_v2(
        channel=dm_channel_id,
        file=file_path,
        initial_comment="전체 제출내역 입니다!",
    )


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
