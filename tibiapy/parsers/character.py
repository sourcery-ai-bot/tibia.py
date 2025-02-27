"""Models related to the Tibia.com character page."""
import re
from collections import OrderedDict
from typing import List, TYPE_CHECKING

from bs4 import Tag

from tibiapy.enums import AccountStatus, Sex, Vocation
from tibiapy.errors import InvalidContent
from tibiapy.models import Achievement, Character, AccountBadge, AccountInformation, OtherCharacter, Killer, \
    Death, GuildMembership, CharacterHouse
from tibiapy.utils import (parse_popup, parse_tibia_date, parse_tibia_datetime, parse_tibiacom_content, split_list,
                           try_enum, parse_link_info)

if TYPE_CHECKING:
    import bs4

# Extracts the scheduled deletion date of a character."""
deleted_regexp = re.compile(r'([^,]+), will be deleted at (.*)')
# Extracts the death's level and killers.
death_regexp = re.compile(r'Level (?P<level>\d+) by (?P<killers>.*)\.</td>')
# From the killers list, filters out the assists.
death_assisted = re.compile(r'(?P<killers>.+)\.<br/>Assisted by (?P<assists>.+)')
# From a killer entry, extracts the summoned creature
death_summon = re.compile(r'(?P<summon>an? .+) of (?P<name>[^<]+)')
link_search = re.compile(r'<a[^>]+>[^<]+</a>')
# Extracts the contents of a tag
link_content = re.compile(r'>([^<]+)<')

house_regexp = re.compile(r'paid until (.*)')

title_regexp = re.compile(r'(.*)\((\d+) titles? unlocked\)')
badge_popup_regexp = re.compile(r"\$\(this\),\s+'([^']+)',\s+'([^']+)',")

traded_label = "(traded)"

__all__ = (
    "CharacterParser",
)


class CharacterParser:

    # region Public methods
    @classmethod
    def from_content(cls, content):
        """Create an instance of the class from the html content of the character's page.

        Parameters
        ----------
        content: :class:`str`
            The HTML content of the page.

        Returns
        -------
        :class:`Character`
            The character contained in the page, or None if the character doesn't exist

        Raises
        ------
        InvalidContent
            If content is not the HTML of a character's page.
        """
        parsed_content = parse_tibiacom_content(content)
        tables = cls._parse_tables(parsed_content)
        data = {}
        if not tables:

            messsage_table = parsed_content.select_one("div.TableContainer")
            if messsage_table and "Could not find character" in messsage_table.text:
                return None
        if "Character Information" in tables.keys():
            cls._parse_character_information(data, tables["Character Information"])
        else:
            raise InvalidContent("content does not contain a tibia.com character information page.")
        data["achievements"] = cls._parse_achievements(tables.get("Account Achievements", []))
        if "Account Badges" in tables:
            data["account_badges"] = cls._parse_badges(tables["Account Badges"])
        cls._parse_deaths(tables.get("Character Deaths", []))
        data["account_information"] = cls._parse_account_information(tables.get("Account Information", []))
        data["other_characters"] = cls._parse_other_characters(tables.get("Characters", []))
        return Character.parse_obj(data)
    # endregion

    # region Private methods
    @classmethod
    def _parse_account_information(cls, rows):
        """Parse the character's account information.

        Parameters
        ----------
        rows: :class:`list` of :class:`bs4.Tag`, optional
            A list of all rows contained in the table.
        """
        acc_info = {}
        if not rows:
            return
        for row in rows:
            cols_raw = row.select('td')
            cols = [ele.text.strip() for ele in cols_raw]
            field, value = cols
            field = field.replace("\xa0", "_").replace(" ", "_").replace(":", "").lower()
            value = value.replace("\xa0", " ")
            acc_info[field] = value
        created = parse_tibia_datetime(acc_info["created"])
        loyalty_title = None if acc_info["loyalty_title"] == "(no title)" else acc_info["loyalty_title"]
        position = acc_info.get("position")
        return AccountInformation(created=created, loyalty_title=loyalty_title, position=position)

    @classmethod
    def _parse_achievements(cls, rows):
        """Parse the character's displayed achievements.

        Parameters
        ----------
        rows: :class:`list` of :class:`bs4.Tag`
            A list of all rows contained in the table.
        """
        achievements = []
        for row in rows:
            cols = row.select('td')
            if len(cols) != 2:
                continue
            field, value = cols
            grade = str(field).count("achievement-grade-symbol")
            name = value.text.strip()
            secret_image = value.find("img")
            secret = False
            if secret_image:
                secret = True
            achievements.append(Achievement(name=name, grade=grade, secret=secret))
        return achievements

    @classmethod
    def _parse_badges(cls, rows: List[Tag]):
        """Parse the character's displayed badges.

        Parameters
        ----------
        rows: :class:`list` of :class:`bs4.Tag`
            A list of all rows contained in the table.
        """
        row = rows[0]
        columns = row.select('td')
        account_badges = []
        for column in columns:
            popup_span = column.select_one("span.HelperDivIndicator")
            if not popup_span:
                # Badges are visible, but none selected.
                return
            popup = parse_popup(popup_span['onmouseover'])
            name = popup[0]
            description = popup[1].text
            icon_image = column.select_one("img")
            icon_url = icon_image['src']
            account_badges.append(AccountBadge(name=name, icon_url=icon_url, description=description))
        return account_badges

    @classmethod
    def _parse_character_information(cls, data, rows):
        """
        Parse the character's basic information and applies the found values.

        Parameters
        ----------
        rows: :class:`list` of :class:`bs4.Tag`
            A list of all rows contained in the table.
        """
        int_rows = ["level", "achievement_points"]
        houses = []
        for row in rows:
            cols_raw = row.select('td')
            cols = [ele.text.strip() for ele in cols_raw]
            field, value = cols
            field = field.replace("\xa0", "_").replace(" ", "_").replace(":", "").lower()
            value = value.replace("\xa0", " ")
            # This is a special case because we need to see the link
            if field == "house":
                house_text = value
                m = house_regexp.search(house_text)
                if not m:
                    continue
                paid_until = m.group(1)
                paid_until_date = parse_tibia_date(paid_until)
                house_link_tag = cols_raw[1].find('a')
                if not house_link_tag:
                    continue
                house_link = parse_link_info(house_link_tag)
                houses.append({
                    "id": house_link["query"]["houseid"],
                    "name": house_link["text"],
                    "town": house_link["query"]["town"],
                    "paid_until": paid_until_date,
                })
                continue
            if field == "guild_membership":
                guild_link = cols_raw[1].select_one('a')
                rank = value.split("of the")[0]
                data["guild_membership"] = GuildMembership(guild_link.text.replace("\xa0", " "), rank.strip())

                continue
            if field in int_rows:
                value = int(value)
            data[field] = value

        if m := deleted_regexp.match(data["name"]):
            data["name"] = m.group(1)
            data["deletion_date"] = parse_tibia_datetime(m.group(2))

        if traded_label in data["name"]:
            data["name"] = data["name"].replace(traded_label, "").strip()
            data["traded"] = True

        if "former_names" in data:
            former_names = [fn.strip() for fn in data["former_names"].split(",")]
            data["former_names"] = former_names

        if "never" in data["last_login"]:
            data["last_login"] = None
        else:
            data["last_login"] = parse_tibia_datetime(data["last_login"])

        if m := title_regexp.match(data.get("title", "")):
            name = m.group(1).strip()
            unlocked = int(m.group(2))
            if name == "None":
                name = None
            data["title"] = name
            data["unlocked_titles"] = unlocked

        data["vocation"] = try_enum(Vocation, data["vocation"])
        data["sex"] = try_enum(Sex, data["sex"])
        data["account_status"] = try_enum(AccountStatus, data["account_status"])

        data["houses"] = [CharacterHouse(h["id"], h["name"], data["world"], h["town"], data["name"], h["paid_until"])
                          for h in houses]

    @classmethod
    def _parse_deaths(cls, data, rows):
        """Parse the character's recent deaths.

        Parameters
        ----------
        rows: :class:`list` of :class:`bs4.Tag`
            A list of all rows contained in the table.
        """
        data["deaths"] = []
        for row in rows:
            cols = row.select('td')
            if len(cols) != 2:
                data["deaths_truncated"] = True
                break
            death_time_str = cols[0].text.replace("\xa0", " ").strip()
            death_time = parse_tibia_datetime(death_time_str)
            death = str(cols[1])
            if not (death_info := death_regexp.search(death)):
                continue
            level = int(death_info.group("level"))
            killers_desc = death_info.group("killers")
            death = Death(name=data["name"], level=level, time=death_time)
            assists_name_list = []
            if assist_match := death_assisted.search(killers_desc):
                # Filter out assists
                killers_desc = assist_match.group("killers")
                # Split assists into a list.
                assists_desc = assist_match.group("assists")
                assists_name_list = link_search.findall(assists_desc)
            killers_name_list = split_list(killers_desc)
            for killer in killers_name_list:
                killer = killer.replace("\xa0", " ")
                killer_dict = cls._parse_killer(killer)
                death.killers.append(Killer(**killer_dict))
            for assist in assists_name_list:
                # Extract names from character links in assists list.
                assist = assist.replace("\xa0", " ")
                assist_dict = cls._parse_killer(assist)
                death.assists.append(Killer(**assist_dict))
            try:
                data["deaths"].append(death)
            except ValueError:
                # Some pvp deaths have no level, so they are raising a ValueError, they will be ignored for now.
                continue

    @classmethod
    def _parse_killer(cls, killer):
        """Parse a killer into a dictionary.

        Parameters
        ----------
        killer: :class:`str`
            The killer's raw HTML string.

        Returns
        -------
        :class:`dict`: A dictionary containing the killer's info.
        """
        # If the killer contains a link, it is a player.
        name = killer
        player = False
        traded = False
        summon = None
        if traded_label in killer:
            name = killer.replace('\xa0', ' ').replace(traded_label, "").strip()
            traded = True
            player = True
        if "href" in killer:
            m = link_content.search(killer)
            name = m.group(1)
            player = True
        if m := death_summon.search(name):
            summon = m.group("summon").replace('\xa0', ' ').strip()
            name = m.group("name").replace('\xa0', ' ').strip()
        return {"name": name, "player": player, "summon": summon, "traded": traded}

    @classmethod
    def _parse_other_characters(cls, rows):
        """Parse the character's other visible characters.

        Parameters
        ----------
        rows: :class:`list` of :class:`bs4.Tag`
            A list of all rows contained in the table.
        """
        other_characters = []
        for row in rows[1:]:
            cols_raw = row.select('td')
            cols = [ele.text.strip() for ele in cols_raw]
            if len(cols) != 4:
                continue
            name, world, status, *__ = cols
            _, *name = name.replace("\xa0", " ").split(" ")
            name = " ".join(name)
            traded = False
            if traded_label in name:
                name = name.replace(traded_label, "").strip()
                traded = True
            main_img = cols_raw[0].select_one('img')
            main = False
            if main_img and main_img['title'] == "Main Character":
                main = True
            position = None
            if "CipSoft Member" in status:
                position = "CipSoft Member"
            other_characters.append(OtherCharacter(name=name, world=world, online="online" in status,
                                                   deleted="deleted" in status, main=main, position=position,
                                                   traded=traded))
        return other_characters


    @classmethod
    def _parse_tables(cls, parsed_content):
        """
        Parse the information tables contained in a character's page.

        Parameters
        ----------
        parsed_content: :class:`bs4.BeautifulSoup`
            A :class:`BeautifulSoup` object containing all the content.

        Returns
        -------
        :class:`OrderedDict`[str, :class:`list`of :class:`bs4.Tag`]
            A dictionary containing all the table rows, with the table headers as keys.
        """
        tables = parsed_content.select('table[width="100%"]')
        output = OrderedDict()
        for table in tables:
            if container := table.find_parent("div", {"class": "TableContainer"}):
                caption_container = container.select_one("div.CaptionContainer")
                title = caption_container.text.strip()
                offset = 0
            else:
                title = table.select_one("td").text.strip()
                offset = 1
            output[title] = table.select("tr")[offset:]
        return output
    # endregion
