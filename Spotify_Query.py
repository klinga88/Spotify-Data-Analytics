#Andrew Kling
#UNCC Project 2 - Spotify Data Analytics
#Using the Spotipy API wrapper pull back favorite artists (top 5 songs), following artists (top 5 songs) and
#all songs on playlists created or followed by the user.  Using the audio features determine if the song fits
#into one of three categories: happy, neutral or sad.  A integer will be passed to the main function which
#indicates what category of song to return.  Given the category the application will return a spotify track
#UID randomly in that category.


import spotipy
import spotipy.util as util
from spotipy.oauth2 import SpotifyClientCredentials
import json
import pandas as pd
import users
from scipy import stats
from sklearn.cluster import KMeans
from scipy.spatial.distance import cdist
from scipy import stats
import plotly
import plotly.plotly as py
import plotly.graph_objs as go
import random
import numpy as np
import math
import os

cid = "4acff433ba4c4b1e97a5cacdb6358f52"
secret = "bcd9bc8e6123468085c44fa911a613ad"
redirect_uri = 'http://localhost:8888/callback/'
scope = 'user-library-read user-top-read user-follow-read'

f = open("output.txt", "w")
data=[] # data for plotly plot

#############################
#Functions
#############################

def authenticate_spotify():
    print('trying spotify...')
    sp = spotipy.Spotify(auth=token)
    return sp

#return list of all user playlists
#format
def get_user_playlists(username):
    playlists = sp.user_playlists(username)
    user_playlists = []
    while playlists:
        for i, playlist in enumerate(playlists['items']):
            playlist_name = playlist['name']
            playlist_id = playlist["uri"].split(":")[4]
            user_playlists.append({"Playlist Name":playlist_name,"Playlist ID": playlist_id})
        if playlists['next']:
            playlists = sp.next(playlists)
        else:
            playlists = None       
    user_playlists_df = pd.DataFrame(user_playlists)
    return(user_playlists_df)
#
#get tracks in each playlist
def get_tracks_in_playlist(playlist_id,username):
    track_details = []
    sp_playlist = sp.user_playlist_tracks(username, playlist_id)
    tracks = sp_playlist['items']
    
    #get each song, song URI, artist, artist URI, album, album URI, album img url
    for i in range(len(tracks)):
        try:
            song_name = tracks[i]["track"]["name"]
            song_uri = tracks[i]["track"]["uri"]
            
            album_name = tracks[i]["track"]["album"]["name"]
            album_uri = tracks[i]["track"]["album"]["uri"]
            
            popularity = tracks[i]["track"]["popularity"]
        except Exception as e:
            print(f"Exception on track number {i},  {e}")
        try:
            artist_name = tracks[i]["track"]["artists"][0]["name"]# @TODO Update to get all artists on track not just first util
            artist_uri = tracks[i]["track"]["artists"][0]["uri"]
        except Exception as e:
            print(f"Exception on track number {i}, no artists listed, {e}")
            artist_name = None
            artist_uir = None
        # try:
        #     album_img = tracks[i]["track"]["album"]["images"][0]["url"]
        # except Exception as e:
        #     print(f"Exception on track number {i}, {album_name}-{artist_name} no album image, {e}")
        #     album_img = [None]
        
    
    track_features = get_track_features(song_uri)
    if track_features is None:  
        track_features = [{'danceability':0,'energy':0,'speechiness':0,'instrumentalness':0,'liveness':0,'valence':0,'tempo':0}]
    track_details.append({"Username":username,"User Playlist ID":playlist_id,"Song Name":song_name,"Song URI":song_uri,"Artist Name":artist_name,"Artist URI":artist_uri,"Album Name":album_name,
                                  "Album URI":album_uri,"Popularity":popularity,"danceability":track_features[0]['danceability'],
                                  "energy":track_features[0]['energy'],"speechiness":track_features[0]['speechiness'],"instrumentalness":track_features[0]['instrumentalness'],
                                  "liveness":track_features[0]['liveness'],"valence":track_features[0]['valence'],"tempo":track_features[0]['tempo']})
    track_details_df = pd.DataFrame(track_details)
    return(track_details_df)

def get_track_features(track_uri):
    #check if URI needs to be split
    if ':' in track_uri:
        track_uri = track_uri.split(":")[2]
    track_features = sp.audio_features(track_uri)
    if None in track_features:
        return(None)
    return(track_features)

#provide a list of all user tracks - output of get_tracks_in_playlist as a list
#return the average audio features of all tracks provided
def get_avg_features(user_tracks):
    danceability=0
    energy=0
    speechiness=0
    instrumentalness=0
    liveness=0
    valence=0
    tempo=0
    num_tracks = len(user_tracks)
    if num_tracks > 0:
        for i in range(len(user_tracks)):
            try:
                danceability += user_tracks[i][0]['Features'][0]['danceability']
                energy += user_tracks[i][0]["Features"][0]["energy"]
                speechiness += user_tracks[i][0]["Features"][0]["speechiness"]
                instrumentalness +=user_tracks[i][0]["Features"][0]["instrumentalness"]
                liveness += user_tracks[i][0]["Features"][0]["liveness"]
                valence += user_tracks[i][0]["Features"][0]["valence"]
                tempo += user_tracks[i][0]["Features"][0]["tempo"]
            except Exception as e:
                print(f"Exception in averaging features, do not exist! {e}")
        
        danceability=danceability/num_tracks
        energy=energy/num_tracks
        speechiness=speechiness/num_tracks
        instrumentalness=instrumentalness/num_tracks
        liveness=liveness/num_tracks
        valence=valence/num_tracks
        tempo=tempo/num_tracks
        avg_features = {"danceability":danceability,"energy":energy,"speechiness":speechiness,"instrumentalness":instrumentalness,
                        "liveness":liveness,"valence":valence,"tempo":tempo}
        return(avg_features)

def get_user_fav_artists(username):
    artists = []
    time_span = ['short_term','medium_term','long_term']
    for time in time_span:
        user_top_artists = sp.current_user_top_artists(limit=50,time_range=time)
        for artist in user_top_artists['items']:
            if artist['name'] not in artists:
                artists.append({"Name":artist['name'],"UID":artist['uri']})
    
    user_followed_artists = sp.current_user_followed_artists(limt=50)
    for artist in user_followed_artists['artists']['items']:
        if artist['name'] not in artists:
            artists.append({"Name":artist['name'],"UID":artist['uri']})

    artists_df = pd.DataFrame(artists)
    return(artists_df)

#function takes a dataframe and returns a bucketed and sorted dataframe based on the audio features of the tracks
def assign_songs_mood(music_df):
    music_df['Mood'] = music_df['valence'] + music_df['energy'] + music_df['danceability']
    music_df['Mood'] = music_df['Mood'].apply(lambda x: math.ceil(x))
    return(music_df)

# emotion_metric = {
#                0:'anger',
#                1:'contempt',
#                2:'disgust',
#                3:'fear',
#                4:'happiness',
#                5:'neutral',
#                6:'sadness',
#                7:'surprise'}
#mood is an int either 3 = happy, 2 = neutral, 1 = sad
#maps string mood to number mood
def map_mood(mood):
    if mood in ['anger','contempt','disgust','fear','sadness']:
        return(1)
    elif mood in ['happiness']:
        return(3)
    else:
        return(2)

def radar_plot_track(track,username):
    data = [go.Scatterpolar(
    r = [track['valence'],track['energy'],track['danceability']],
    theta = ['Valence','Energy','Danceability','Valence'],
    fill = 'toself'
    )]

    layout = go.Layout(
    title = f'{username} | {track["Song Name"]}',
    polar = dict(
        radialaxis = dict(
        visible = True,
        range = [0,1]
        )
    ),
    showlegend = False
    )

    fig = go.Figure(data=data, layout=layout)
    py.iplot(fig)

def get_song_for_mood(mood,username):
    mood = map_mood(mood)
    all_user_tracks_df = pd.DataFrame()

    #if user has spotify username, get their data.  else use top 200 csv
    if username is not None:
        user_playlists_df = get_user_playlists(username)
        for playlist_id in user_playlists_df["Playlist ID"]:
            track_details_df = get_tracks_in_playlist(playlist_id,username)
            all_user_tracks_df = all_user_tracks_df.append(track_details_df)
    else:
        top_100_df =  get_top_music()
        all_user_tracks_df  =  top_100_df
    
    #if user doesnt have enough songs use the top 200 csv
    if all_user_tracks_df['Song URI'].count() < 25:
        #Add songs from top 200
        top_100_df =  get_top_music()
        all_user_tracks_df  =  top_100_df
    all_user_tracks_df = assign_songs_mood(all_user_tracks_df)
    #get just songs with the mood we want
    mood_tracks_df  = all_user_tracks_df.loc[all_user_tracks_df['Mood'] == mood,:]
    #get random track
    rand_idx = random.randint(0, mood_tracks_df['Song URI'].count()-1)
    track = mood_tracks_df.iloc[rand_idx,:]
    radar_plot_track(track,username)
    return(track)

#reads in csv from spotifycharts.com and get audio features for each song
def get_top_music():
    track_details = []
    music_df = pd.read_csv("music.csv",encoding='latin1', skiprows=1)
    music_df['Track UID'] = music_df['URL'].apply(lambda x: pd.Series(x.split('/')[4]))

    for index, row in music_df.iterrows():
        track_features = get_track_features(row["Track UID"])
        song_name = row['Track Name']
        song_uri = row['URL']
        artist_name = row['Artist']
        
        if track_features is None:  
            track_features = [{'danceability':0,'energy':0,'speechiness':0,'instrumentalness':0,'liveness':0,'valence':0,'tempo':0}]
        track_details.append({"Username":'"SpotifyCharts',"User Playlist ID":'SpotifyCharts',"Song Name":song_name,"Song URI":song_uri,"Artist Name":artist_name,"Artist URI":'SpotifyCharts',
                                  "Album Name":'SpotifyCharts',"Album URI":'SpotifyCharts',"Popularity":'SpotifyCharts',"danceability":track_features[0]['danceability'],
                                  "energy":track_features[0]['energy'],"speechiness":track_features[0]['speechiness'],"instrumentalness":track_features[0]['instrumentalness'],
                                  "liveness":track_features[0]['liveness'],"valence":track_features[0]['valence'],"tempo":track_features[0]['tempo']})
    track_details_df = pd.DataFrame(track_details)
    return(track_details_df) 

########################################
#Application start here
########################################
#Generate an authorization token
client_credentials_manager = SpotifyClientCredentials(cid, secret)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

#find average of top music
top_music_df = get_top_music()
top_music_df = assign_songs_mood(top_music_df)
avg_valence = top_music_df['valence'].mean()
avg_energy = top_music_df['energy'].mean()
avg_danceability = top_music_df['danceability'].mean()

min_track = top_music_df.loc[top_music_df['Mood']==top_music_df['Mood'].min(),:]
min_valence = min_track['valence']
min_energy = min_track['energy']
min_danceability = min_track['danceability']

data = [go.Scatterpolar(
    r = [avg_valence,avg_energy,avg_danceability],
    theta = ['Valence','Energy','Danceability','Valence'],
    fill = 'toself',
    name='Average'
    ),
    go.Scatterpolar(
    r = [min_valence,min_energy,min_danceability],
    theta = ['Valence','Energy','Danceability','Valence'],
    fill = 'toself',
    name=f'Minimum Mood: {min_track["Song Name"]}'
    )]

layout = go.Layout(
title = f'Global Top 200 Songs Average',
polar = dict(
    radialaxis = dict(
    visible = True,
    range = [0,1]
    )
),
showlegend = False
)

fig = go.Figure(data=data, layout=layout)
py.iplot(fig, filename='top200')

for name in users.user_list:
    mood = 'happiness'
    song = get_song_for_mood(mood,name)
    print(f"{name} : {song['Mood']} | {song['Song Name']} - {song['Song URI']}")


    # print(all_user_tracks_df)
    #avg_features = get_avg_features(all_user_tracks)
    # if avg_features is not None:
    #     avg_features = {"valence":avg_features['valence'],"danceability":avg_features['danceability'],
    #                     "energy":avg_features['energy']}
    #     print(f"Username: {username} has features!")
    #     trace=go.Bar(x=list(avg_features.keys()),y=list(avg_features.values()),name=username)
    #     data.append(trace)
    # f.write(json.dumps(all_user_tracks, indent=4))
# #plot data
# print(f"data: {data}")

# layout = go.Layout(
#     barmode='group'
# )
# fig = go.Figure(data=data, layout=layout)
# plotly.offline.plot(fig, filename='grouped-bar.html')