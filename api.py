import datetime
import hashlib
import json
import logging
import uuid
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, HTTPServer

import scoring
import store

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


class AccessError(Exception):
    pass


class Field:
    def __init__(self, value, required, nullable) -> None:
        self.required = required
        self.nullable = nullable
        self.value = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if value is not None or self.nullable:
            self._value = value
        if value is None and self.required:
            raise ValueError(f"Значение не может быть пустым: {self.__class__.__name__}")


class CharField(Field):
    def __init__(self, value, required, nullable) -> None:
        super().__init__(value, required, nullable)
        if self._value is not None:
            if not isinstance(value, str):
                raise ValueError("Значение должно быть строкой", value)
        else:
            self._value = ""


class ArgumentsField(Field):
    def __init__(self, value: dict, required, nullable) -> None:
        super().__init__(value, required, nullable)


class EmailField(CharField):
    def __init__(self, value, required, nullable) -> None:
        super().__init__(value, required, nullable)
        if self.value:
            self._validate()

    def _validate(self):
        if "@" not in self.value:
            raise ValueError("Некорректный email")


class PhoneField(Field):
    def __init__(self, value, required, nullable) -> None:
        super().__init__(value, required, nullable)
        if self._value:
            self._value = str(self._value)
            self._validate()

    def _validate(self):
        if not (len(self._value) == 11 and self._value.startswith("7") and self._value.isdigit()):
            raise ValueError("Некорректный номер телефона")


class DateField(CharField):
    def __init__(self, value, required, nullable) -> None:
        super().__init__(value, required, nullable)
        if self._value:
            self._validate()

    def _validate(self):
        try:
            datetime.datetime.strptime(self._value, "%d.%m.%Y")
        except ValueError:
            raise ValueError("Некорректный формат даты")


class BirthDayField(DateField):
    def __init__(self, value, required, nullable) -> None:
        super().__init__(value, required, nullable)
        if self._value:
            self._validate()

    def _validate(self):
        super()._validate()
        date_tmp = datetime.datetime.strptime(self._value, "%d.%m.%Y")
        seventy_years_ago = datetime.datetime.today() - datetime.timedelta(days=70 * 365.25)
        if date_tmp < seventy_years_ago:
            raise ValueError("Некорректная дата рождения")


class GenderField(Field):
    def __init__(self, value, required, nullable) -> None:
        super().__init__(value, required, nullable)
        if self._value is not None:
            self._validate()

    def _validate(self):
        if self._value not in range(3):
            raise ValueError("Некорректный пол")


class ClientIDsField(Field):
    def __init__(self, value, required) -> None:
        super().__init__(value, required, False)
        self._validate()

    def _validate(self):
        if isinstance(self.value, list):
            if len(self.value) == 0:
                raise ValueError("Массив не может быть пустым")
            if not all(isinstance(i, int) for i in self.value):
                raise ValueError("Члены массива должны быть целым числов")
        else:
            raise ValueError("Поле должно быть массивом")


class ClientsInterestsRequest:
    def __init__(self, argument_dict) -> None:
        self.client_ids = ClientIDsField(argument_dict.get("client_ids"), required=True)
        self.date = DateField(argument_dict.get("date"), required=False, nullable=True)

    def process(self, store):
        output = {str(i): scoring.get_interests(store, i) for i in self.client_ids.value}
        return output


class OnlineScoreRequest:
    def __init__(self, argument_dict) -> None:
        self.first_name = CharField(argument_dict.get("first_name"), required=False, nullable=True)
        self.last_name = CharField(argument_dict.get("last_name"), required=False, nullable=True)
        self.email = EmailField(argument_dict.get("email"), required=False, nullable=True)
        self.phone = PhoneField(argument_dict.get("phone"), required=False, nullable=True)
        self.birthday = BirthDayField(argument_dict.get("birthday"), required=False, nullable=True)
        self.gender = GenderField(argument_dict.get("gender"), required=False, nullable=True)
        if not self._validate():
            raise ValueError("Некорректный набор аргументов для метода online_score")

    def process(self, store):
        return scoring.get_score(
            store,
            self.phone.value,
            self.email.value,
            self.birthday.value,
            self.gender.value,
            self.first_name.value,
            self.last_name.value,
        )

    def _validate(self):
        valid_conditions = []
        valid_conditions.append(all((self.phone.value, self.email.value)))
        valid_conditions.append(all((self.first_name.value, self.last_name.value)))
        valid_conditions.append(all((self.gender.value is not None, self.birthday.value)))
        return any(valid_conditions)


class MethodRequest:
    def __init__(self, body_dict) -> None:
        self.account = CharField(body_dict["account"], required=False, nullable=True)
        self.login = CharField(body_dict["login"], required=True, nullable=True)
        self.token = CharField(body_dict["token"], required=True, nullable=True)
        self.arguments = ArgumentsField(body_dict["arguments"], required=True, nullable=True)
        self.method = CharField(body_dict["method"], required=True, nullable=False)
        if not self._check_auth():
            raise AccessError("Доступ запрещен")

    @property
    def is_admin(self):
        return self.login.value == ADMIN_LOGIN

    def process(self, ctx, store):
        match self.method.value:
            case "online_score":
                if self.login.value == "admin":
                    return {"score": 42}
                out = {"score": OnlineScoreRequest(self.arguments.value).process(store)}
                ctx["has"] = self.arguments.value.keys()
                return out
            case "clients_interests":
                out = ClientsInterestsRequest(self.arguments.value).process(store)
                ctx["nclients"] = len(self.arguments.value.get("client_ids"))
                return out

    def _check_auth(self):
        if self.is_admin:
            digest = hashlib.sha512(
                (datetime.datetime.today().strftime("%Y%m%d%H") + ADMIN_SALT).encode("utf-8")
            ).hexdigest()
        else:
            digest = hashlib.sha512((self.account.value + self.login.value + SALT).encode("utf-8")).hexdigest()
        return digest == self.token.value


def method_handler(request, ctx, store):
    try:
        request = MethodRequest(request.get("body"))

        response, code = request.process(ctx, store), OK
        return response, code
    except ValueError as e:
        logging.exception(e)
        return {"code": INVALID_REQUEST}, INVALID_REQUEST
    except KeyError as e:
        logging.exception(e)
        return {"code": INVALID_REQUEST}, INVALID_REQUEST
    except AccessError as e:
        logging.exception(e)
        return {"code": FORBIDDEN}, FORBIDDEN


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {"method": method_handler}
    store = store.RedisStore()

    def get_request_id(self, headers):
        return headers.get("HTTP_X_REQUEST_ID", uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers["Content-Length"]))
            request = json.loads(data_string)
        except Exception:
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
        self.wfile.write(json.dumps(r).encode("utf-8"))
        return


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", action="store", type=int, default=8080)
    parser.add_argument("-l", "--log", action="store", default=None)
    args = parser.parse_args()
    logging.basicConfig(
        # filename=args.log,
        level=logging.INFO,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S",
        handlers=[logging.StreamHandler()],
    )

    server = HTTPServer(("localhost", args.port), MainHTTPHandler)
    logging.info("Starting server at %s" % args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    # server.server_close()
