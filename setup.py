from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

setup(
    name='django-gcp-cloudtasks',  # Updated package name
    version='1.2.0',
    packages=find_packages(),
    url='https://github.com/dm-nosov/django-cloudtasks', 
    license='MIT',
    author='Dmitry Nosov',
    author_email='nosov.sibers@gmail.com',
    description='Google Cloud Tasks support for Django',
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=[
        'django>=3.2',
        'google-cloud-tasks>=2.13.0',
        'requests>=2.28.2'  
    ],
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.2",
        "Framework :: Django :: 5.0",
    ],
    python_requires='>=3.9',
)
