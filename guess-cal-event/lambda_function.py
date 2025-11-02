from google import genai
from pydantic import BaseModel
import logging
import json
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# event creation: https://developers.google.com/workspace/calendar/api/v3/reference/events/insert
# event resource (definition): https://developers.google.com/workspace/calendar/api/v3/reference/events#resource

"""
{
  "etag": etag,
  "id": string,
  "status": string,
  "htmlLink": string,
  "created": datetime,
  "updated": datetime,
  "summary": string,
  "description": string,
  "location": string,
  "colorId": string,
  "creator": {
    "id": string,
    "email": string,
    "displayName": string,
    "self": boolean
  },
  "organizer": {
    "id": string,
    "email": string,
    "displayName": string,
    "self": boolean
  },
  "start": {
    "date": date,
    "dateTime": datetime,
    "timeZone": string
  },
  "end": {
    "date": date,
    "dateTime": datetime,
    "timeZone": string
  },
  "endTimeUnspecified": boolean,
  "recurrence": [
    string
  ],
  "recurringEventId": string,
  "originalStartTime": {
    "date": date,
    "dateTime": datetime,
    "timeZone": string
  },
  "transparency": string,
  "visibility": string,
  "iCalUID": string,
  "sequence": integer,
  "attendees": [
    {
      "id": string,
      "email": string,
      "displayName": string,
      "organizer": boolean,
      "self": boolean,
      "resource": boolean,
      "optional": boolean,
      "responseStatus": string,
      "comment": string,
      "additionalGuests": integer
    }
  ],
  "attendeesOmitted": boolean,
  "extendedProperties": {
    "private": {
      (key): string
    },
    "shared": {
      (key): string
    }
  },
  "hangoutLink": string,
  "conferenceData": {
    "createRequest": {
      "requestId": string,
      "conferenceSolutionKey": {
        "type": string
      },
      "status": {
        "statusCode": string
      }
    },
    "entryPoints": [
      {
        "entryPointType": string,
        "uri": string,
        "label": string,
        "pin": string,
        "accessCode": string,
        "meetingCode": string,
        "passcode": string,
        "password": string
      }
    ],
    "conferenceSolution": {
      "key": {
        "type": string
      },
      "name": string,
      "iconUri": string
    },
    "conferenceId": string,
    "signature": string,
    "notes": string,
  },
  "gadget": {
    "type": string,
    "title": string,
    "link": string,
    "iconLink": string,
    "width": integer,
    "height": integer,
    "display": string,
    "preferences": {
      (key): string
    }
  },
  "anyoneCanAddSelf": boolean,
  "guestsCanInviteOthers": boolean,
  "guestsCanModify": boolean,
  "guestsCanSeeOtherGuests": boolean,
  "privateCopy": boolean,
  "locked": boolean,
  "reminders": {
    "useDefault": boolean,
    "overrides": [
      {
        "method": string,
        "minutes": integer
      }
    ]
  },
  "source": {
    "url": string,
    "title": string
  },
  "workingLocationProperties": {
    "type": string,
    "homeOffice": (value),
    "customLocation": {
      "label": string
    },
    "officeLocation": {
      "buildingId": string,
      "floorId": string,
      "floorSectionId": string,
      "deskId": string,
      "label": string
    }
  },
  "outOfOfficeProperties": {
    "autoDeclineMode": string,
    "declineMessage": string
  },
  "focusTimeProperties": {
    "autoDeclineMode": string,
    "declineMessage": string,
    "chatStatus": string
  },
  "attachments": [
    {
      "fileUrl": string,
      "title": string,
      "mimeType": string,
      "iconLink": string,
      "fileId": string
    }
  ],
  "birthdayProperties": {
    "contact": string,
    "type": string,
    "customTypeName": string
  },
  "eventType": string
}
"""

"""
My calendar event specification
{
  "htmlLink": string,
  "summary": string,
  "description": string,
  "location": string,
  "start": {
    "date": date,
    "dateTime": datetime,
    "timeZone": string
  },
  "end": {
    "date": date,
    "dateTime": datetime,
    "timeZone": string
  },
  "attachments": [ # not yet
    {
      "fileUrl": string,
      "title": string,
      "mimeType": string,
      "iconLink": string,
      "fileId": string
    }
  ]
}
"""


class EventBoundary(BaseModel):
    date: str | None
    dateTime: str | None
    timeZone: str | None


class Attachment(BaseModel):
    fileUrl: str
    title: str
    mimeType: str
    iconLink: str
    fileId: str


class CalendarEventResponse(BaseModel):
    htmlLink: str | None
    summary: str
    description: str | None
    location: str | None
    start: EventBoundary
    end: EventBoundary


@dataclass
class CurrentTimeInfo:
    d: datetime
    weekday: (int, str)
    iso_time: str


PROMPT_PREFIX = """
You are an expert calendar event generator. Given an input description of an event, generate a JSON object that conforms to the following schema for a Google Calendar event:
Events may also be timed or all-day:
    A timed event occurs between two specific points in time. Timed events use the start.dateTime and end.dateTime fields to specify when they occur.
    An all-day event spans an entire day or consecutive series of days. All-day events use the start.date and end.date fields to specify when they occur. Note that the timezone field has no significance for all-day events.

Assumptions:
    If the user doesn't specify a date, assume it is today.
    If the user doesn't specify a time, assume it is an all-day event.
    If the user specifies a start time but not an end time, assume the event lasts one hour.

The JSON schema is as follows:
{
  "htmlLink": string, # Any link if provided by the user
  "summary": string, # Title of the event (make it concise)
  "description": string, # Description of the event (nicely worded description of event)
  "location": string, # Provided location of the event. If room number such as "GOS 2455" provided, just use that.
  "start": {
    "date": date, # for all-day events
    "dateTime": datetime, # for timed events
    "timeZone": string
  },
  "end": {
    "date": date, # for all-day events
    "dateTime": datetime, # for timed events
    "timeZone": string
  }
}
"""


def get_datetime_info(d: datetime) -> CurrentTimeInfo:
    """

    :param d:
    :return:
    """
    weekday = d.weekday()
    weekday_str = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][weekday]
    iso_time = d.isoformat()
    return CurrentTimeInfo(d=d, weekday=(weekday, weekday_str), iso_time=iso_time)


def get_full_prompt(user_input: str, current_time: CurrentTimeInfo) -> str:
    """

    :param user_input:
    :param current_time:
    :return:
    """
    prompt = PROMPT_PREFIX
    prompt += f'\nCurrent date and time: {current_time.iso_time} (Today is {current_time.weekday[1]})\n'
    prompt += f'User input: {user_input}\n'
    return prompt


def lambda_handler(event, context):
    """
    Take an input and serialize it into a google calendar event.
    Return the event as JSON.
    :param event: schema is
    {
        "input": string,
        "timezone": string (optional) specify using IANA timezone format, e.g. "America/Los_Angeles"
    }
    :param context:
    :return:
    """

    try:
        current_time = datetime.now()
        current_time_info = get_datetime_info(current_time)
        user_input = event['input']
        full_prompt = get_full_prompt(user_input, current_time_info)

        with open('env.json') as f:
            config = json.load(f)

        client = genai.Client(api_key=config['gemini_api_key'])

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=full_prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": CalendarEventResponse,
            },
        )

        body = json.loads(response.text)

        # remove None entries from start and end
        for boundary in ['start', 'end']:
            if boundary in body:
                body_boundary = body[boundary]
                keys_to_remove = [key for key, value in body_boundary.items() if value is None]
                for key in keys_to_remove:
                    del body_boundary[key]

        return {
            'statusCode': 200,
            'body': body
        }
    except Exception as e:
        logger.error(f"Error processing request: {e.with_traceback(None)}")
        # return {
        #     'statusCode': 500,
        #     'body': f"Error processing request: {e}"
        # }
        raise e


if __name__ == '__main__':
    event = {
        'input': "rehearsal on sunday with trio in LBR 264 at 12:30"
    }
    context = {}
    print(lambda_handler(event, context))
