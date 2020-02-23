# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# MapManager
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------

class MapManager(object):
    """Base class for building Folium map visualization.

    Currently, the functionality is limited, but may be extended in the future.

    Work-around for multi-line in popup:
    https://github.com/python-visualization/folium/issues/469

    Popup work-around::

        popup = (
            "Time: {time}<br>"
            "Speed: {speed} km/h<br>"
        ).format(time=row.name.strftime('%H:%M'),
                 speed=str(round(row['spd'],2))


    Tooltip doesn't yet work in 0.50.0:<br>
    https://github.com/python-visualization/folium/issues/785
    Update: in 0.6.0 (WSL1.2.3) it does seem to work!
    """


    kansas_city_coord = [39.085594, -94.585241]  # Kansas City, roughly the geographic center of the USA

    def __init__(self, data_manager=None, location=None, zoom_start=1, width='100%', height='100%',
                 layer_control_position='topleft'):
        import folium  # Import here so that you only do the import if you are actually using this class
        self.dm = data_manager
        self.location = location
        self.zoom_start = zoom_start
        self.width = width
        self.height = height
        self.layer_control_position = layer_control_position

    def create_blank_map(self):
        import folium
        m = folium.Map(location=self.location, zoom_start=self.zoom_start, tiles='cartodbpositron', width=self.width,
                       height=self.height)
        return m

    def add_layer_control(self, m):
        import folium
        # Typical value = `topleft`
        if self.layer_control_position is not None:
            folium.LayerControl(position=self.layer_control_position).add_to(m)

    @staticmethod
    def add_full_screen(m):
        """Adds a full-screen button in the top-left corner of the map.
        Unfortunately, the full-screen doesn't work in a Jupyter cell.
        Seems to work ok here: http://nbviewer.jupyter.org/github/python-visualization/folium/blob/master/examples/Plugins.ipynb"""
        from folium import plugins
        plugins.Fullscreen(position='topleft',
                           title='Expand me',
                           title_cancel='Exit me',
                           force_separate_button=True).add_to(m)


    #---------------------------------------------------------------------------------------------------------
    # Arrows
    #---------------------------------------------------------------------------------------------------------
    @staticmethod
    def get_bearing(p1, p2):
        """
        Returns compass bearing from p1 to p2

        Parameters
        p1 : namedtuple with lat lon
        p2 : namedtuple with lat lon

        Return
        compass bearing of type float

        Notes
        Based on https://gist.github.com/jeromer/2005586
        """
        import numpy as np
        long_diff = np.radians(p2.lon - p1.lon)

        lat1 = np.radians(p1.lat)
        lat2 = np.radians(p2.lat)

        x = np.sin(long_diff) * np.cos(lat2)
        y = (np.cos(lat1) * np.sin(lat2)
             - (np.sin(lat1) * np.cos(lat2)
                * np.cos(long_diff)))

        bearing = np.degrees(np.arctan2(x, y))

        # adjusting for compass bearing
        if bearing < 0:
            return bearing + 360
        return bearing

    @staticmethod
    def get_arrows(locations, color='blue', size=6, n_arrows=3, add_to=None):
        """Add arrows to a hypothetical line between the first 2 locations in the locations list.
        Get a list of correctly placed and rotated arrows/markers to be plotted.

        Args:
            locations : List of lists of lat lon that represent the
                        start and end of the line.
                        eg [[41.1132, -96.1993],[41.3810, -95.8021]]
                        The locations is a list so that it matches the input for the folium.PolyLine.
            color : Whatever folium can use.  Default is 'blue'
            size : Size of arrow. Default is 6
            n_arrows : Number of arrows to create.  Default is 3.
            add_to: map or FeatureGroup the arrows are added to.

        Returns:
            list of arrows/markers

        Based on: https://medium.com/@bobhaffner/folium-lines-with-arrows-25a0fe88e4e
        """
        # TODO: generalize so that locations can be any length >=2, i.e. a PolyLine with more than 1 section.

        import folium
        from collections import namedtuple
        import numpy as np
        Point = namedtuple('Point', field_names=['lat', 'lon'])

        # creating point from our Point named tuple
        p1 = Point(locations[0][0], locations[0][1])
        p2 = Point(locations[1][0], locations[1][1])

        # getting the rotation needed for our marker.
        # Subtracting 90 to account for the marker's orientation
        # of due East(get_bearing returns North)
        rotation = MapManager.get_bearing(p1, p2) - 90

        # get an evenly space list of lats and lons for our arrows
        # note that I'm discarding the first and last for aesthetics
        # as I'm using markers to denote the start and end
        arrow_lats = np.linspace(p1.lat, p2.lat, n_arrows + 2)[1:n_arrows + 1]
        arrow_lons = np.linspace(p1.lon, p2.lon, n_arrows + 2)[1:n_arrows + 1]

        arrows = []

        # creating each "arrow" and appending them to our arrows list
        for points in zip(arrow_lats, arrow_lons):
            arrows.append(folium.RegularPolygonMarker(location=points,
                                                      fill_color=color, number_of_sides=3,
                                                      radius=size, rotation=rotation).add_to(add_to))
        return arrows

    # @staticmethod
    # def get_arrows_2(from_location, to_location, color='blue', size=6, n_arrows=3, add_to=None):
    #     """Add arrows to a hypothetical line between the locations.
    #     Get a list of correctly placed and rotated arrows/markers to be plotted.
    #
    #     Args:
    #         from_location (lat,lon): from location as a tuple or list with lat and lon, e.g. [41.1132, -96.1993]
    #         to_location (lat,lon): from location as a tuple or list with lat and lon, e.g. [41.3810, -95.8021]
    #         color : Whatever folium can use.  Default is 'blue'
    #         size : Size of arrow. Default is 6
    #         n_arrows : Number of arrows to create.  Default is 3.
    #         add_to: map or FeatureGroup the arrows are added to.
    #
    #     Returns:
    #         list of arrows/markers
    #     """
    #     from collections import namedtuple
    #     import numpy as np
    #     Point = namedtuple('Point', field_names=['lat', 'lon'])
    #
    #     # creating point from our Point named tuple
    #     p1 = Point(from_location[0], from_location[1])
    #     p2 = Point(to_location[0], to_location[1])
    #
    #     # getting the rotation needed for our marker.
    #     # Subtracting 90 to account for the marker's orientation
    #     # of due East(get_bearing returns North)
    #     rotation = MapManager.get_bearing(p1, p2) - 90
    #
    #     # get an evenly space list of lats and lons for our arrows
    #     # note that I'm discarding the first and last for aesthetics
    #     # as I'm using markers to denote the start and end
    #     arrow_lats = np.linspace(p1.lat, p2.lat, n_arrows + 2)[1:n_arrows + 1]
    #     arrow_lons = np.linspace(p1.lon, p2.lon, n_arrows + 2)[1:n_arrows + 1]
    #
    #     arrows = []
    #
    #     # creating each "arrow" and appending them to our arrows list
    #     for points in zip(arrow_lats, arrow_lons):
    #         arrows.append(folium.RegularPolygonMarker(location=points,
    #                                                   fill_color=color, number_of_sides=3,
    #                                                   radius=size, rotation=rotation).add_to(add_to))
    #     return arrows

    @staticmethod
    def get_html_table(rows):
        """Creates 2 column html table for use in popups.
        Args:
            rows: List of sequences. Each sequence should have 2 string entries, one for each column

        Returns:
            html: a HTML formatted table of two columns
        """
        table_html_pattern = """<table style="width:100%">{}</table>"""
        # row_html_pattern = """<tr><td>{}:&nbsp</td><td>{}</td></tr>"""
        row_html_pattern = """<tr><td>{}&nbsp</td><td>{}</td></tr>"""
        rows_html = ''
        for row in rows:
            rows_html = rows_html + '\n' + row_html_pattern.format(row[0], row[1])
        html = table_html_pattern.format(rows_html)
        return html

    @staticmethod
    def get_popup_table(rows):
        """Return a popup table to add as a popup/child to a folium element.

        Usage::

            popup_table = [
            ]
            popup = MapManager.get_popup_table(popup_table)

        Next, the popup object can be used in a popup argument of a Marker::

            marker = folium.Marker(coord,
                               popup=popup,
                               icon=icon
                               )

        Or added as a child::

            county.add_child(popup)

        Args:
            rows: List of sequences. Each sequence should have 2 string entries, one for each column.

        Returns:
            popup (folium.Popup)

        Notes
        Beware that a quote in the texts causes a problem (no map shows).
        This can be avoided by replacing the "\'" with something else.
        Unfortunately the option `parse_html=True` does not prevent the problem.
        Despite the suggestion in https://nbviewer.jupyter.org/github/python-visualization/folium/blob/master/examples/Popups.ipynb
        """
        import folium
        html_text = MapManager.get_html_table(rows)
        html = folium.Html(html_text, script=True)
        popup = folium.Popup(html, parse_html=True, max_width=2650)
        return popup

