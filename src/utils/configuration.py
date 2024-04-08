import yaml

DEFAULT_JIRA_URL = "https://issues.redhat.com"
DEFAULT_SUBQUERY = ""


class Config:
    @staticmethod
    def load(config_file: str) -> dict:
        with open(config_file, "r") as yaml_file:
            config = yaml.safe_load(yaml_file)
        return config

    @staticmethod
    def validate(config: dict) -> None:
        if "jira" not in config.keys():
            raise RuntimeError("Missing 'jira' object in the configuration file")
        for key in ["project-id"]:
            if key not in config["jira"].keys():
                raise RuntimeError(
                    f"Missing 'jira/{key}' object in the configuration file"
                )
        config["jira"]["url"] = config["jira"].get("url", DEFAULT_JIRA_URL)
        config["jira"]["subquery"] = config["jira"].get("subquery", DEFAULT_SUBQUERY)
        config["comments"] = config.get("comments", {})
        config["comments"]["footer"] = config["comments"].get("footer", "")
