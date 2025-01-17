import abc
import json
import datetime
import logging
import hashlib
import uuid
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, HTTPServer
import scoring

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}



def check_empty(value, nullable):
    return value==None and not nullable


class Field:
    
    def __init__(self, value, required, nullable) -> None:
        self.required = required
        self.nullable = nullable
        self._value = value
    
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self,value):
        if value is not None or self.nullable:
            self._value = value
        if value is None and  self.required: 
            raise ValueError(f"Значение не может быть пустым: {self.__class__.__name__}")



class CharField(Field):
    
    def __init__(self, value:str, required, nullable) -> None:
        super().__init__(value, required, nullable)

class ArgumentsField(Field):
    
    def __init__(self, value:dict, required, nullable) -> None:
        super().__init__(value, required, nullable)


class EmailField(CharField):
    
    def __init__(self, value, required, nullable) -> None:
        super().__init__(value, required, nullable)

    @CharField.value.setter
    def value(self,value):
        super().value = value
        if self.value:
            if not '@' in value:
                raise ValueError("Некорректный email")
        self._value = value


class PhoneField(CharField):
    
    def __init__(self, value, required, nullable) -> None:
        super().__init__(value, required, nullable)

    @CharField.value.setter
    def value(self,phone_number):
        phone = str(phone_number)
        if not (len(phone) == 11 and phone.startswith('7') and phone.isdigit()):
            raise ValueError("Некорректный номер телефона")
        self._value = phone


class DateField(object):
    pass
    



class BirthDayField(CharField):
    
    def __init__(self, value, required, nullable) -> None:
        super().__init__(self, value, required, nullable)

    @CharField.value.setter
    def value(self,date):
        try:
            date_tmp = datetime.datetime.strptime(date, "%d.%m.%Y")
        except ValueError:
            raise ValueError("Некорректный формат даты")

        seventy_years_ago =  datetime.datetime.today() - datetime.timedelta(days=70 * 365.25)
        if date_tmp < seventy_years_ago:
            raise ValueError("Некорректная дата рождения")
        self._value = date


class GenderField(CharField):
    
    def __init__(self, value, required, nullable) -> None:
        super().__init__(self, value, required, nullable)

    @property
    def gender(self):
        return self._gender

    @gender.setter
    def gender(self,gender):
        if not gender in range(3):
            raise ValueError("Некорректный пол")
        self._gender = gender


class ClientIDsField(object):
    pass


#class ClientsInterestsRequest(ArgumentsField):
#    client_ids = ClientIDsField(required=True)
#    date = DateField(required=False, nullable=True)


class OnlineScoreRequest:

    def __init__(self, argument_dict) -> None:
        self.first_name = CharField(argument_dict.get("first_name"), required=False, nullable=True)
        self.last_name = CharField(argument_dict.get("last_name"), required=False, nullable=True)
        self.email = EmailField(argument_dict.get("email"), required=False, nullable=True)
        self.phone = PhoneField(argument_dict.get("phone"),required=False, nullable=True)
        self.birthday = BirthDayField(argument_dict.get("birthday"),required=False, nullable=True)
        self.gender = GenderField(argument_dict.get("gender"),required=False, nullable=True)




class MethodRequest:
    def __init__(self, body_dict) -> None:    
        self.account = CharField(body_dict['account'], required=False, nullable=True)
        self.login = CharField(body_dict['login'],required=True, nullable=True)
        self.token = CharField(body_dict['token'],required=True, nullable=True)
        self.arguments = ArgumentsField(body_dict['arguments'],required=True, nullable=True)
        self.method = CharField(body_dict['method'],required=True, nullable=False)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN


def check_auth(request):
    if request.is_admin:
        digest = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode('utf-8')).hexdigest()
    else:
        digest = hashlib.sha512((request.account + request.login + SALT).encode('utf-8')).hexdigest()
    return digest == request.token


def method_handler(request, ctx, store):
    try:
        request = MethodRequest(request.get("body"))
        ctx["has"] = request.arguments.value.keys()
        response, code = None, None
        return response, code
    except ValueError as e:
        return {"code"}, FORBIDDEN
    except KeyError:
        return {}, INVALID_REQUEST


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {
        "method": method_handler
    }
    store = None

    def get_request_id(self, headers):
        return headers.get('HTTP_X_REQUEST_ID', uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            request = json.loads(data_string)
        except:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path]({"body": request, "headers": self.headers}, context, self.store)
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r).encode('utf-8'))
        return


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", action="store", type=int, default=8080)
    parser.add_argument("-l", "--log", action="store", default=None)
    args = parser.parse_args()
    logging.basicConfig(filename=args.log, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", args.port), MainHTTPHandler)
    logging.info("Starting server at %s" % args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()