class XxxManager:

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def shutdown_instance(cls):
        if cls._instance is not None:
            cls._instance.cleanup()
            cls._instance = None



    def __init__(self):
        pass



    def cleanup(self):
        pass
