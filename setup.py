from setuptools import setup, find_packages

setup(
    name="frogubot",
    version="0.2.6",
    packages=find_packages(),
    install_requires=[
        "kurigram",
        "httpx"
    ],
    entry_points={
        "console_scripts": [
            "frogubot=frogubot.cli:start_bot",
            "frogubot-setup=frogubot.cli:setup_wizard",
        ],
    },
    description="FrogUBot Client Engine",
)
