from collections import defaultdict
import sqlite3
import json
import subprocess
from os import path
import datetime
import collections
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
from mpl_toolkits.basemap import Basemap

class TweetCoord:
    def __init__(self, dbname):
        self.dbname = dbname
        self.f_name = None

    def tweet_coord(self):
        """"""
        conn = sqlite3.connect(self.dbname)
        c = conn.cursor()

        coordinates = c.execute("SELECT COORDINATES "
                                "FROM TWEET, PLACE "
                                "WHERE TWEET.PLACE_ID = PLACE.PLACE_ID").fetchall()

        conn.close()
        return coordinates

    def coord_time(self):
        """Obtain tweet spatial coordinates along with the time of their creation"""
        conn = sqlite3.connect(self.dbname)
        c = conn.cursor()

        coordinates = c.execute("SELECT COORDINATES, CREATED_AT "
                                "FROM TWEET, PLACE "
                                "WHERE TWEET.PLACE_ID = PLACE.PLACE_ID").fetchall()

        conn.close()
        return coordinates

    def save_coord(self, f_name="coords"):
        """Save the coordinates of all tweets from the database in a 'f_name' file.
           In the file, the lat and long are separated by a whitespace, and a linebreak
           separates each pair of coordinates.

           Parameters:
           ----------
           f_name: str
                  Name of the file where the coordinates must be stored.
        """
        self.f_name = f_name
        coordinates = self.tweet_coord()

        with open(f_name, 'w') as output_file:
            for coord in coordinates:
                data = json.loads(coord[0])
                output_file.write("{} {}\n".format(data[1], data[0]))

class TweetHeatMap:
    def __init__(self, dbname, config=None):
        self.dbname = dbname
        self.coords = TweetCoord(dbname)
        self.coords.save_coord()
        coord_path = path.abspath(self.coords.f_name)
        self.config = {"-p": "-p {}".format(coord_path), "o": "-o heatmap.png", "width": "--width=2000",
                       "osm": "--osm", "B": "-B 0.8", "osm_base": "--osm_base=http://tile.openstreetmap.org"}

        if config is not None:
            self.config.update(config)

        self.heatmap_path = "./heatmap/heatmap.py"

    def heatmap(self):
        args = [self.heatmap_path]
        for value in self.config.itervalues():
            args.append(value)

        print(args)
        proc = subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if stderr != "":
            raise Exception(stderr)

class AnimatedAggregatedTweets:
    """Create an animated map with tweets aggregated by time windows of timedelta units of time"""

    def __init__(self,dbname,timedelta,interval=200):
        self.dbname = dbname
        self.time_coord = TweetCoord(dbname).coord_time() # contains both time of tweet creation and geolocalisation
        self.timedelta = timedelta # should be a datetime.timdelta object representing the size of the time window
        self.aggregate = defaultdict(list) # dictionnary of coordinates indexed by time windows
        self.interval = interval # update animation each interval millisec

    def time_window(self):
        """Aggregate tweets in time windows of timedelta time to monitor the temporal evolution"""

        ## Ensure that tweets are ordered by date
        processed = []
        for tc in self.time_coord:
            ## Decode string format to python objects
            coords = json.loads(tc[0])
            created_at = datetime.datetime.strptime(tc[1], "%a %b %d %H:%M:%S +0000 %Y")
            processed.append((coords, created_at))

        ## Sort them by date
        time_ordered = sorted(processed, key=lambda x: x[1])

        ## Aggregate tweets in time windows of duration timedelta
        first_time = time_ordered[0][1]

        for e in time_ordered:
            if e[1] < first_time + self.timedelta:
                if first_time not in self.aggregate:
                    self.aggregate[first_time] = [e[0]]
                else:
                    self.aggregate[first_time].append(e[0])
            else:
                while e[1] > first_time + self.timedelta:
                    first_time = first_time + self.timedelta
                    self.aggregate[first_time] = []

                self.aggregate[first_time] = [e[0]]

    def animated_map(self):
        """Plot the animated map"""
        self.time_window()
        self.aggregate = collections.OrderedDict(sorted(self.aggregate.items() , key=lambda t: t[0]))
        map = Basemap(projection='cyl', resolution=None, lat_0=0., lon_0=0.)
        map.bluemarble()

        x,y = map(0,0)
        points = []
        for k in self.aggregate.keys():
            points.append(map.plot(x,y,'o', markerfacecolor = 'yellow', markeredgecolor= 'none' ,alpha=.5, markersize=3)[0])

        def animate(i):
            """subroutine to update points"""
            lon = np.asarray(self.aggregate.values()[i])[:,0]
            lat = np.asarray(self.aggregate.values()[i])[:,1]
            for pt,lon,lat in zip(points, lon, lat):
                x, y = map(lon,lat)
                pt.set_data(x, y)

            plt.title('%s (UTC)' % self.aggregate.keys()[i])
            return points

        frm = len(self.aggregate)
        anim = animation.FuncAnimation(plt.gcf(), animate, frames=frm, interval=200)

        #anim.save('movie.mp4')

        plt.show()

delta = datetime.timedelta(0,0,0,0,1) # aggregate by one minute slices (we should use bigger delta with a bigger db)
am = AnimatedAggregatedTweets("tweets.db", delta, 100)
am.animated_map()
