NAME = 'Travel Network'
PREFIX = '/video/travel'
ICON = 'icon-default.jpg'

BASE_URL = 'http://www.travelchannel.com'

FULLEPS = 'http://www.travelchannel.com/video/full-episodes'
SHOWS = 'http://www.travelchannel.com/shows'

SMIL_NS = {'a': 'http://www.w3.org/2005/SMIL21/Language'}

####################################################################################################
def Start():

    ObjectContainer.title1 = NAME
    DirectoryObject.thumb = R(ICON)
    HTTP.CacheTime = CACHE_1HOUR

####################################################################################################
@handler(PREFIX, NAME, thumb=ICON)
def MainMenu():

    oc = ObjectContainer()

    oc.add(DirectoryObject(key = Callback(FullEpisodes, title='Full Episodes', url=FULLEPS), title='Full Episodes'))
    oc.add(DirectoryObject(key = Callback(MoreShows, title='Shows'), title='Shows'))

    return oc

####################################################################################################
# This function produces a list of all of the playlist items from the ful episodes page
@route(PREFIX + '/fullepisodes')
def FullEpisodes(title, url):

    oc = ObjectContainer(title2=title)
    page = HTML.ElementFromURL(url)

    # Create playlist elements from the headers for each show section
    playlist = page.xpath('//div[contains(@class, "contentwell-container")]//section[@class="jukebox-wrapper "]')

    for item in playlist:
        title = item.xpath('./header/h2//text()')[0].strip()
        try: url = BASE_URL + item.xpath('./header/a/@href')[0]
        except: continue
        oc.add(DirectoryObject(key = Callback(VideoBrowse, title=title, url=url), title=title))

    if len(oc) < 1:
        return ObjectContainer(header='Empty', message='There are no items to list')
    else:
        return oc

####################################################################################################
# This function produces a list of more shows
@route(PREFIX + '/moreshows')
def MoreShows(title):

    oc = ObjectContainer(title2=title)
    page = HTML.ElementFromURL(SHOWS, cacheTime = CACHE_1DAY)

    for show in page.xpath('//div[@class="bulletedList-wrapper"]//li/a'):

        title = show.text
        show_url = BASE_URL + show.xpath('./@href')[0]

        oc.add(DirectoryObject(
            key = Callback(GetVideoLinks, show_url=show_url, title=title),
            title = title
        ))

    if len(oc) < 1:
        return ObjectContainer(header='Empty', message='There are no shows to list')
    else:
        return oc

####################################################################################################
# This function pulls the video link from a show's main page
@route(PREFIX + '/getvideolink')
def GetVideoLinks(title, show_url):

    oc = ObjectContainer(title2=title)
    page = HTML.ElementFromURL(show_url, cacheTime = CACHE_1DAY)

    # The Videos link can vary 
    for item in page.xpath('//li[contains(@class, "subNavigationItem")]'):

        section_title = item.xpath('./a/text()')[0].strip()
        # Skip any the navigation items that are not for videos
        if 'video' not in section_title.lower() and 'full episodes' not in section_title.lower():
            continue
        section_url = item.xpath('./a/@href')[0]

        if not section_url.startswith('http://'):
           section_url = BASE_URL + section_url

        oc.add(DirectoryObject(
            key = Callback(VideoBrowse, url=section_url, title=section_title),
            title=section_title
        ))

    if len(oc) < 1:
        return ObjectContainer(header='Empty', message='There are no videos for this show')
    else:
        return oc

####################################################################################################
# This function produces a list of videos from a playlist
@route(PREFIX + '/videobrowse')
def VideoBrowse(url, title):

    oc = ObjectContainer(title2=title)
    page = HTML.ElementFromURL(url)

    json_list = page.xpath('//div[@class="videoplaylist-item"]/@data-videoplaylist-data')

    for video in json_list:
        try: json = JSON.ObjectFromString(video)
        except: json = None

        if json:
            smil_url = json['releaseUrl']
            if 'link.theplatform.com' in smil_url:
                oc.add(
                    CreateVideoClipObject(
                        smil_url = smil_url,
                        title = json['title'].replace('&amp,', '&').replace('&apos;', "'"),
                        summary = json['description'],
                        duration = Datetime.MillisecondsFromString(json['duration']),
                        thumb = BASE_URL + json['thumbnailUrl']
                    )
                )

    if len(oc) < 1:
        return ObjectContainer(header='Empty', message='There are currently no videos for this listing')
    else:
        return oc

####################################################################################################
@route(PREFIX + '/createvideoclipobject', duration=int, include_container=bool)
def CreateVideoClipObject(smil_url, title, summary, duration, thumb, include_container=False, **kwargs):

    videoclip_obj = VideoClipObject(
        key = Callback(CreateVideoClipObject, smil_url=smil_url, title=title, summary=summary, duration=duration, thumb=thumb, include_container=True),
        rating_key = smil_url,
        title = title,
        summary = summary,
        duration = duration,
        thumb = Resource.ContentsOfURLWithFallback(url=thumb),
        items = [
            MediaObject(
                parts = [
                    PartObject(key=Callback(PlayVideo, smil_url=smil_url, resolution=resolution))
                ],
                container = Container.MP4,
                video_codec = VideoCodec.H264,
                audio_codec = AudioCodec.AAC,
                audio_channels = 2,
                video_resolution = resolution
            ) for resolution in [720, 540, 480]
        ]
    )

    if include_container:
        return ObjectContainer(objects=[videoclip_obj])
    else:
        return videoclip_obj

####################################################################################################
@route(PREFIX + '/playvideo', resolution=int)
@indirect
def PlayVideo(smil_url, resolution):

    xml = XML.ElementFromURL(smil_url)
    available_versions = xml.xpath('//a:switch[1]/a:video/@height', namespaces=SMIL_NS)

    if len(available_versions) < 1:
        raise Ex.MediaNotAvailable

    closest = min((abs(int(resolution) - int(i)), i) for i in available_versions)[1]
    video_url = xml.xpath('//a:switch[1]/a:video[@height="%s"]/@src' % closest, namespaces=SMIL_NS)[0]

    return IndirectResponse(VideoClipObject, key=video_url)
