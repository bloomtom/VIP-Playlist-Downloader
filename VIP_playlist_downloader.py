from ctypes import windll, create_string_buffer
import xml.etree.ElementTree as ET
import sys, os, os, math, requests, struct, argparse, re, traceback

# EVENTUAL TRANSCODING WILL USE THIS: https://github.com/devsnd/python-audiotranscode

namehacks = {
    # trailing dot
    '\.{2,}m4a': '.m4a',

    # .dothack
    '^\.hack': 'dothack',
    # '^dothack\S': 'dothack - ', # kasdjfkajsbdflkbsadf

    # Original Version despacing & parenthesizing
    '  Original Version': ' (Original Version)',

    # Double space to dash
    '\s\s': ' - ',

    # Pokemon name fixing
    'TimeDarknessSky': 'Time-Darkness-Sky',
    'RedBlueYellow': 'Red-Blue-Yellow',
    'GoldSilverCrystal': 'Gold-Silver-Crystal',
    'BlackWhite': 'Black & White',

    # Ecco vocal remix
    'MaskVocal Remix': 'Mask (Vocal Remix)',

    # FFVII X'mas edit
    "  X'mas Edit": " (X'mas Edit)"
}

def get_term_size():
    h = windll.kernel32.GetStdHandle(-12)
    csbi = create_string_buffer(22)
    res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)
    (bufx, bufy, curx, cury, wattr,
        left, top, right, bottom, maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
    sizex = right - left + 1
    sizey = bottom - top + 1
    return sizex, sizey

def getPrettyFileSizes(fsize, size = None):
    frd = lambda s,d: round(float(s)/1000**d,2)
    sizelist = { 'B' : fsize, 'KB' : frd(fsize,1), 'MB' : frd(fsize,2), 'GB' : frd(fsize,3)}
    if size is None:
        if fsize < 1.0: return 0, 'B'
        for sls in sizelist:
            if 1 <= sizelist[sls] <= 1000:
                return sizelist[sls], sls
        return sizelist['MB'], 'MB' # bleh testing is too hard
    else:
        return sizelist.get(size)

def download(song, total_songs, current_song, location = ''):

    file_size_dl = 0
    block_sz = 8192

    filePath = os.path.join(location, song.filename)

    try:
        with requests.get(song.location) as r:
            r.raise_for_status()
            if (r.is_redirect or (r.history and len(r.history) > 0 and r.history[0].is_redirect)):
                if (r.url == 'https://www.vipvgm.net/'):
                    raise Exception(f'404 at address {song.location}.')
                print(f'URL redirect followed: {song.location} => {r.url}.')

            with open(filePath, 'wb') as f:
                for c in r.iter_content(chunk_size=block_sz):
                    f.write(c)

        postoutput = "\r[%4d/%4d] %s" % (current_song, total_songs, song.filename) + ' ' * 80
        print(postoutput[:get_term_size()[0]-1])

    except Exception as e:
        if os.path.exists(filePath):
            os.remove(filePath)
        print('\n[Error] ' + str(e))
        print(f'[Error] Download failed. Skipping: {song.creator} - {song.title}.\n')

def download_song(song, total_songs, current_song, location='', legacy=False):
    if not os.path.exists(location):
        os.makedirs(location)

    if legacy:
        download(song, total_songs, current_song, location)
    else:
        print('[%4d/%4d] Downloading: %s' % (current_song, total_songs, song.filename))
        with open(os.path.join(location, song.filename), 'wb') as f:
            try:
                f.write(song.data)
            except:
                f.close()
                print; print('Stopping download and exiting.')
                sys.exit()
            finally:
                f.close()


def apply_namehacks(filename):
    for hack in namehacks:
        filename = re.sub(hack, namehacks[hack], filename)
    return filename


class Song(object):
    import requests

    def __init__(self, creator, title, location, getfsizes=False, verbose=False):
        self.verbose = verbose

        self.creator = creator
        self.title = title
        self.location = location

        self.filename = creator + ' - ' + title + '.m4a'
        self.raw_filename = self.filename
        self.vlog("Creating filename: %s -> %s" % (self.location, self.filename))

        self.filename = self.filename.replace('"',"'")
        self.filename = ''.join([c for c in self.filename if c not in '\/:*?<>|'])
        self.vlog("Sanitizing filename: %s -> %s" % (self.raw_filename, self.filename))

        self._filesize = None
        self._human_filesize = None

        if getfsizes:
            self._filesize = self.filesize
            self._human_filesize = self.human_filesize


    @property
    def filesize(self):
        if not self._filesize:
            try:
                self._filesize = int(requests.head(self.location).headers['content-length'])
            except Exception:
                self._filesize = 0
            
            self.vlog("Got filesize for '%s': %s" % (self.filename, self._filesize))

        return self._filesize

    @property
    def human_filesize(self):
        if not self._human_filesize:
            self._human_filesize = str(getPrettyFileSizes(self.filesize, 'MB')) + ' MB'
            self.vlog("Got human filesize for '%s': %s" % (self.filename, self._human_filesize))

        return self._human_filesize

    @property
    def data(self):
        r = requests.get(self.location)
        self._filesize = int(r.headers['content-length'])
        self._human_filesize = str(getPrettyFileSizes(self._filesize, 'MB')) + ' MB'

        return r.content

    def vlog(self, text):
        if self.verbose:
            print(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('VIP Playlist Downloader', epilog='Epilog text')

    parser.add_argument('-c', '--check-size', help='Verify local file matches remote file', action='store_true', dest='dl_sizecheck')
    parser.add_argument('-d', '--download-method', help='Which download method to use', choices=['fancy', 'boring'], default='fancy', dest='dl_method')
    parser.add_argument('-f', '--folder', help='Download destination folder', default='VIP Playlist', dest='dl_folder')
    parser.add_argument('-l', '--list', help='List files only, no download', action='store_true', dest='listonly')
    parser.add_argument('-n', '--no-namehacks', help='Do not apply namehacks', action='store_true', dest='dl_nonamehacks')
    parser.add_argument('-o', '--overwrite', help='Download files that would be skipped', action='store_true', dest='dl_overwrite')
    parser.add_argument('-p', '--playlist', help='Which playlist to download', choices=['normal', 'source', 'mellow', 'exiled', 'anime', 'couch'], default='normal', dest='dl_playlist')
    parser.add_argument('-r', '--no-redownload', help='Do not redownload files that differ in size from the remote file', action='store_true', dest='dl_noredownload')
    parser.add_argument('-v', '--verbose', help='Output extra information', action='store_true', dest='verbose')
    parser.add_argument('-V', '--version', help='Print version and exit', action='store_true', dest='version')

    # TODO: Add:
    #   alternate XML roster location/ remove normal playlist assumptions


    clargs = parser.parse_args()

    try:
        if [True for c in clargs.dl_folder if c in ':*?<>|']:
            print(NameError("Error: Download folder cannot be named %s" % clargs.dl_folder))
            sys.exit(1)

        print("Preparing to download latest VIP playlist")

        rosternames = {
            'normal': 'https://vip.aersia.net/roster.xml',
            'source': 'https://vip.aersia.net/roster-source.xml',
            'mellow': 'https://vip.aersia.net/roster-mellow.xml',
            'exiled': 'https://vip.aersia.net/roster-exiled.xml',
            'anime':  'https://wap.aersia.net/roster.xml',
            'couch':  'https://cpp.aersia.net/roster.xml'
        }

        xmlroster = rosternames[clargs.dl_playlist]

        roster = requests.get(xmlroster)
        treeroot = ET.fromstring(re.sub('xmlns="(.*?)"', '', roster.text))
        tracks = treeroot.find('trackList')
        print(tracks[0].find('title').text)

        songlist = []
        numnamehacks = 0
        skipMatch = re.compile('(^Vidya Intarweb Playlist.*|^MOTD\s\d{1,}/\d{1,}/\d{1,}|^Changelog|^Notice$|^Notice\s[IVX]{1,}|^All Tracks$)')
        
        for track in tracks:
            song_creator = track.find('creator').text

            matches = skipMatch.search(song_creator)
            if (matches and len(matches[0]) == len(song_creator)):
                continue

            song_title = track.find('title').text
            song_location = track.find('location').text

            song = Song(song_creator, song_title, song_location)

            if not clargs.dl_nonamehacks:
                oldfilename = song.filename
                song.filename = apply_namehacks(song.filename)
                if song.filename != oldfilename:
                    if clargs.verbose:
                        print("Applied namehack:\n%s ->\n%s\n" % (oldfilename, song.filename))
                    numnamehacks += 1

            songlist.append(song)

        print("Applied %s namehacks" % numnamehacks)
        print('Beginning downloads to: %s' % os.path.join(os.path.abspath('.'), clargs.dl_folder))
        print()

        total_song_data_size = 0
        downloaded_songs = 0
        total_songs = len(songlist)

        for song in songlist:
            try:
                if clargs.dl_overwrite:
                    raise Exception # Silly hack but it works

                if song.filename in os.listdir(clargs.dl_folder):
                    if clargs.dl_sizecheck:
                        songsmatch = os.path.getsize(os.path.join(clargs.dl_folder, song.filename)) == song.filesize
                    else:
                        songsmatch = True

                    if songsmatch:
                        print("[Skip]", song.filename)
                        downloaded_songs += 1
                        continue
                    else:
                        if clargs.dl_noredownload:
                            print("[Skip]", song.filename)
                        else:
                            print("[Redownload]", song.filename)
            except Exception as e:
                pass

            if not clargs.listonly:
                download_song(song, total_songs, downloaded_songs+1, clargs.dl_folder, legacy=clargs.dl_method=='fancy')
                total_song_data_size += song.filesize
            else:
                print("[%4d/%4d] %s" % (downloaded_songs+1, total_songs, song.filename))

            downloaded_songs += 1

        print("All done.")
    except KeyboardInterrupt:
        print("\nControl C caught, exiting.")

    except Exception as e:
        traceback.print_stack()

    finally:
        # tdsize = 'GB' if total_song_data_size >= 1000000000 else 'MB'
        # print "Total data downloaded: %s %s" % (getPrettyFileSizes(total_song_data_size, tdsize), tdsize)
        print("Total data downloaded: %s %s" % getPrettyFileSizes(total_song_data_size))

