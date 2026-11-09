# *****************************************************************************
# define Python user-defined exceptions
class RinexModError(Exception):
    pass


class RinexModInputArgsError(RinexModError):
    pass


class RinexFileError(RinexModError):
    pass


class MetaDataError(RinexModError):
    pass


class ReturnListError(RinexModError):
    pass
