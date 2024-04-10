import re
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
from .regex_fns import whitespace_regex


def replace_imgs_w_alts(images):
    for img in images:
        # if the image has alt text, use it
        if img.has_attr("alt"):
            # print("🔥 image has alt text", img["alt"])
            img.string = img["alt"]
        # otherwise, remove the image
        else:
            img.decompose()


def html2md(
    html_content,
):
    """
    inputs:
        - html_content: html content from a web page
    outputs:
        - text: text from the html content
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # remove all style and scripts
    for data in soup(["style", "script"]):
        data.decompose()

    # for a in soup.find_all("a", href=True):
    #    a.replace_with(a.text)  # replace links with their text

    # FIXME: replace all images with their alt text
    images = soup.find_all("img", alt="")
    replace_imgs_w_alts(images)
    cells = soup.find_all("td")
    for td in cells:
        td_text = td.text.strip()
        # replace any long internal whitespace with a single space
        td_text = re.sub(whitespace_regex, " ", td_text)
        td.string = td_text

    markdown = MarkdownConverter(heading_style="ATX").convert(str(soup))
    markdown = markdown.replace("\r\n", "\n")
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def html2md_clean(
    html_content,
):
    """
    inputs:
        - html_content: html content from a web page
    outputs:
        - text: text from the html content
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # remove all style and scripts
    for data in soup(["style", "script"]):
        data.decompose()

    for a in soup.find_all("a", href=True):
        a.replace_with(a.text)  # replace links with their text

    # FIXME: replace all images with their alt text
    images = soup.find_all("img", alt="")
    replace_imgs_w_alts(images)
    cells = soup.find_all("td")
    for td in cells:
        td_text = td.text.strip()
        # replace any long internal whitespace with a single space
        td_text = re.sub(whitespace_regex, " ", td_text)
        td.string = td_text

    markdown = MarkdownConverter(heading_style="ATX").convert(str(soup))
    markdown = markdown.replace("\r\n", "\n")
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()
