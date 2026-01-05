"""
Music playback tools for J.A.R.V.I.S.
Controls Apple Music via AppleScript and YouTube Music via browser.
Based on proven implementation with better timeout handling.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
from typing import Optional

import httpx
from livekit.agents import llm

logger = logging.getLogger(__name__)

# Optional YouTube Music support
try:
    from ytmusicapi import YTMusic
    YTMUSIC_AVAILABLE = True
except ImportError:
    YTMUSIC_AVAILABLE = False
    YTMusic = None


async def _run_applescript(script: str, timeout: float = 15.0) -> tuple[bool, str]:
    """Execute AppleScript and return success status and output."""
    if platform.system() != "Darwin":
        return False, "Music control only available on macOS"

    try:
        process = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        output = stdout.decode().strip() if stdout else stderr.decode().strip()
        return process.returncode == 0, output
    except asyncio.TimeoutError:
        # Try to kill the process
        try:
            process.kill()
        except Exception:
            pass
        return False, "Command timed out - Music app may need to be opened first"
    except Exception as e:
        return False, str(e)


async def _ensure_music_running() -> bool:
    """Ensure Music.app is running, launch if needed."""
    # Check if Music is running
    check_script = 'tell application "System Events" to (name of processes) contains "Music"'
    success, output = await _run_applescript(check_script, timeout=5.0)

    if success and output.lower() == "true":
        return True

    # Launch Music
    try:
        process = await asyncio.create_subprocess_exec(
            "open", "-a", "Music",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(process.communicate(), timeout=5.0)
        await asyncio.sleep(2.0)  # Give it time to start
        return True
    except Exception:
        return False


async def _open_media_link(url: str, app: str | None = None) -> tuple[bool, str]:
    """Open a URL in the appropriate media player/browser."""
    system = platform.system()

    if system == "Windows":
        try:
            await asyncio.to_thread(os.startfile, url)  # type: ignore[attr-defined]
            return True, ""
        except OSError as exc:
            return False, str(exc)

    if system == "Darwin":
        cmd = ["open"]
        if app:
            cmd.extend(["-a", app])
        cmd.append(url)
    else:
        opener = "xdg-open"
        cmd = [opener, url]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode().strip() if stdout else stderr.decode().strip()
        return process.returncode == 0, output
    except FileNotFoundError:
        try:
            import webbrowser

            if webbrowser.open(url):
                return True, "Opened via webbrowser"
        except Exception:
            pass
        return False, f"Could not launch opener: {cmd[0]}"
    except Exception as exc:
        return False, str(exc)


async def _open_in_music_app(url: str) -> tuple[bool, str]:
    """Open an Apple Music URL directly in Music.app and start playback."""
    if platform.system() != "Darwin":
        return False, "Apple Music playback is only available on macOS."

    escaped = url.replace('"', '\\"')
    script = f'''
    tell application "Music"
        try
            activate
            open location "{escaped}"
            delay 1.0
            play
            return "OK"
        on error errMsg number errNum
            return errMsg
        end try
    end tell
    '''
    return await _run_applescript(script, timeout=15.0)


class AppleMusicController:
    """Control Apple Music via AppleScript on macOS."""

    async def play(self) -> str:
        """Resume playback."""
        script = 'tell application "Music" to play'
        success, output = await _run_applescript(script)
        return "Resuming playback" if success else f"Failed to resume: {output}"

    async def pause(self) -> str:
        """Pause playback."""
        script = 'tell application "Music" to pause'
        success, output = await _run_applescript(script)
        return "Paused" if success else f"Failed to pause: {output}"

    async def stop(self) -> str:
        """Stop playback."""
        script = 'tell application "Music" to stop'
        success, output = await _run_applescript(script)
        return "Stopped" if success else f"Failed to stop: {output}"

    async def next_track(self) -> str:
        """Skip to next track."""
        script = 'tell application "Music" to next track'
        success, output = await _run_applescript(script)
        return "Skipping to next track" if success else f"Failed to skip: {output}"

    async def previous_track(self) -> str:
        """Go to previous track."""
        script = 'tell application "Music" to previous track'
        success, output = await _run_applescript(script)
        return "Going to previous track" if success else f"Failed: {output}"

    async def get_current_track(self) -> str:
        """Get info about currently playing track."""
        script = '''
        tell application "Music"
            if player state is playing then
                set track_name to name of current track
                set artist_name to artist of current track
                set album_name to album of current track
                return track_name & " by " & artist_name & " from " & album_name
            else if player state is paused then
                set track_name to name of current track
                set artist_name to artist of current track
                return track_name & " by " & artist_name & " (paused)"
            else
                return "Nothing is playing"
            end if
        end tell
        '''
        success, output = await _run_applescript(script)
        return output if success else "Could not get track info"

    async def set_volume(self, level: int) -> str:
        """Set volume (0-100)."""
        level = max(0, min(100, level))
        script = f'tell application "Music" to set sound volume to {level}'
        success, output = await _run_applescript(script)
        return f"Volume set to {level}%" if success else f"Failed: {output}"

    async def get_volume(self) -> str:
        """Get current volume."""
        script = 'tell application "Music" to get sound volume'
        success, output = await _run_applescript(script)
        if success:
            return f"Volume is at {output}%"
        return "Could not get volume"

    async def play_playlist(self, name: str) -> str:
        """Play a specific playlist by name."""
        name = name.replace('"', '\\"')
        script = f'''
        tell application "Music"
            try
                set targetPlaylist to first playlist whose name is "{name}"
                play targetPlaylist
                return "Playing playlist: {name}"
            on error
                return "Playlist not found: {name}"
            end try
        end tell
        '''
        success, output = await _run_applescript(script)
        return output if output else "Failed to play playlist"

    async def play_catalog(self, query: str, search_type: str = "track") -> tuple[bool, str, Optional[str]]:
        """Play content from the Apple Music catalog."""
        if platform.system() != "Darwin":
            return False, "Apple Music playback is only available on macOS.", "unsupported"

        item, reason = await self._catalog_search(query, search_type)
        if reason == "error":
            return False, "Apple Music search failed. Check your internet connection.", reason
        if reason == "not_found" or not item:
            return False, f"Couldn't find {search_type} '{query}' on Apple Music.", "not_found"

        url = self._catalog_url(item, search_type)
        if not url:
            return False, "Apple Music returned an incomplete result.", "error"

        candidate_urls = [url]
        if url.startswith("https://"):
            candidate_urls.insert(0, url.replace("https://", "music://", 1))

        success = False
        output = ""
        for target_url in candidate_urls:
            success, output = await _open_in_music_app(target_url)
            if success:
                break

        if not success:
            fallback_success, fallback_output = await _open_media_link(url, app="Music")
            if fallback_success:
                output = "Opened link in Music—tap play if it doesn't start automatically."
            else:
                output = fallback_output or output

        description = self._catalog_description(item, search_type, query)
        prefix_map = {
            "artist": "Playing songs by",
            "album": "Playing album",
            "track": "Playing",
        }
        prefix = prefix_map.get(search_type, "Playing")
        if success:
            return True, f"{prefix} {description} on Apple Music", None

        fallback = f"Open this link in Apple Music: {url}"
        if output:
            fallback = f"{fallback} ({output})"
        return False, fallback, "open_failed"

    async def _catalog_search(self, query: str, search_type: str) -> tuple[Optional[dict], Optional[str]]:
        """Search the public Apple Music catalog."""
        entity = "musicTrack"
        if search_type == "artist":
            entity = "musicArtist"
        elif search_type == "album":
            entity = "album"

        params = {
            "term": query,
            "media": "music",
            "limit": 1,
            "entity": entity,
        }

        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                response = await client.get("https://itunes.apple.com/search", params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Apple Music catalog search failed: %s", exc)
            return None, "error"

        try:
            data = response.json()
        except ValueError as exc:
            logger.warning("Invalid Apple Music response: %s", exc)
            return None, "error"

        results = data.get("results") or []
        if not results:
            return None, "not_found"
        return results[0], None

    def _catalog_url(self, item: dict, search_type: str) -> Optional[str]:
        """Extract a playable Apple Music URL from a search result."""
        url_fields = {
            "track": ["trackViewUrl", "collectionViewUrl"],
            "album": ["collectionViewUrl", "trackViewUrl"],
            "artist": ["artistLinkUrl", "artistViewUrl"],
        }

        for field in url_fields.get(search_type, []):
            url = item.get(field)
            if url:
                return url

        for fallback in ("trackViewUrl", "collectionViewUrl", "artistLinkUrl", "artistViewUrl"):
            url = item.get(fallback)
            if url:
                return url
        return None

    def _catalog_description(self, item: dict, search_type: str, default: str) -> str:
        """Build a friendly description for catalog playback."""
        if search_type == "artist":
            return item.get("artistName") or default

        if search_type == "album":
            album = item.get("collectionName") or default
            artist = item.get("artistName")
            return f"{album} by {artist}" if artist else album

        title = item.get("trackName") or item.get("collectionName") or default
        artist = item.get("artistName")
        return f"{title} by {artist}" if artist else title

    async def search_and_play(self, query: str, search_type: str = "track") -> str:
        """Search for and play a track, artist, or album."""
        query = query.replace('"', '\\"')

        if search_type == "artist":
            script = f'''
            tell application "Music"
                try
                    set results to (every track whose artist contains "{query}")
                    if (count of results) > 0 then
                        play item 1 of results
                        return "Playing songs by {query}"
                    else
                        return "No songs found by {query}"
                    end if
                on error
                    return "Could not search for artist"
                end try
            end tell
            '''
        elif search_type == "album":
            script = f'''
            tell application "Music"
                try
                    set results to (every track whose album contains "{query}")
                    if (count of results) > 0 then
                        play item 1 of results
                        return "Playing album: {query}"
                    else
                        return "Album not found: {query}"
                    end if
                on error
                    return "Could not search for album"
                end try
            end tell
            '''
        else:  # track
            script = f'''
            tell application "Music"
                try
                    set results to (every track whose name contains "{query}")
                    if (count of results) > 0 then
                        play item 1 of results
                        return "Playing: {query}"
                    else
                        return "Track not found: {query}"
                    end if
                on error
                    return "Could not search for track"
                end try
            end tell
            '''

        success, output = await _run_applescript(script)
        return output if output else f"Failed to play {query}"

    async def shuffle(self, enabled: bool = True) -> str:
        """Enable or disable shuffle."""
        mode = "true" if enabled else "false"
        script = f'tell application "Music" to set shuffle enabled to {mode}'
        success, output = await _run_applescript(script)
        state = "on" if enabled else "off"
        return f"Shuffle {state}" if success else f"Failed: {output}"

    async def repeat(self, mode: str = "all") -> str:
        """Set repeat mode: off, one, all."""
        mode_map = {"off": "off", "one": "one", "all": "all", "song": "one", "playlist": "all"}
        repeat_mode = mode_map.get(mode.lower(), "off")
        script = f'tell application "Music" to set song repeat to {repeat_mode}'
        success, output = await _run_applescript(script)
        return f"Repeat set to {repeat_mode}" if success else f"Failed: {output}"


class YouTubeMusicController:
    """Search and play YouTube Music content."""

    def __init__(self):
        self.yt = YTMusic() if YTMUSIC_AVAILABLE else None

    def search(self, query: str, filter_type: str = None) -> str:
        """Search YouTube Music and return top results."""
        if not self.yt:
            return "YouTube Music not available (install ytmusicapi)"

        try:
            results = self.yt.search(query, filter=filter_type, limit=3)
            if not results:
                return f"No results for: {query}"

            items = []
            for r in results[:3]:
                title = r.get("title", "Unknown")
                artists = ", ".join([a["name"] for a in r.get("artists", [])])
                type_str = r.get("resultType", "")
                if artists:
                    items.append(f"{title} by {artists} ({type_str})")
                else:
                    items.append(f"{title} ({type_str})")

            return "Found: " + "; ".join(items)
        except Exception as e:
            return f"Search failed: {e}"

    def get_url(self, query: str) -> tuple[Optional[str], str]:
        """Get a direct YouTube Music URL for a search query."""
        if not self.yt:
            return None, "YouTube Music playback requires ytmusicapi. Run `pip install ytmusicapi`."

        try:
            filters = ["songs", "videos", None]
            for filter_type in filters:
                results = self.yt.search(query, filter=filter_type, limit=1)
                if not results:
                    continue
                item = results[0]
                video_id = item.get("videoId")
                if not video_id:
                    continue
                title = item.get("title", "Unknown title")
                artists = ", ".join([a["name"] for a in item.get("artists", [])])
                description = f"{title} by {artists}" if artists else title
                return f"https://music.youtube.com/watch?v={video_id}", description
        except Exception as exc:
            logger.exception("YouTube Music search failed: %s", exc)
            return None, f"YouTube Music search failed: {exc}"

        return None, f"No results for '{query}' on YouTube Music"

    async def play(self, query: str) -> str:
        """Search and play a track on YouTube Music."""
        url, description = self.get_url(query)
        if not url:
            return description

        success, output = await _open_media_link(url)
        if success:
            return f"Playing {description} on YouTube Music"

        fallback = f"Open this link to play: {url}"
        if output:
            fallback = f"{fallback} ({output})"
        return fallback


# Initialize controllers
apple_music = AppleMusicController()
youtube_music = YouTubeMusicController()


@llm.function_tool
async def music_play(query: str = "", provider: str = "apple") -> str:
    """
    Play music. Can search and play specific songs, artists, albums, or playlists.

    Args:
        query: What to play (song name, artist, album, or playlist). Empty to resume.
        provider: 'apple' for Apple Music, 'youtube' for YouTube Music
    """
    provider = provider.lower()

    if provider == "youtube":
        if not query:
            return "Please specify what to search for on YouTube Music"
        return await youtube_music.play(query)

    # Apple Music - ensure app is running first
    await _ensure_music_running()

    if not query:
        return await apple_music.play()

    query_lower = query.lower()

    async def _play_with_catalog(target: str, search_type: str) -> str:
        success, message, reason = await apple_music.play_catalog(target, search_type)
        if success:
            return message
        if reason in {"not_found", "error"}:
            fallback = await apple_music.search_and_play(target, search_type)
            if fallback.lower().startswith("playing"):
                return fallback
            if reason == "not_found":
                return fallback
        return message

    # Check for playlist
    if "playlist" in query_lower:
        match = re.search(r'playlist[:\s]+(.+)', query, re.IGNORECASE)
        if match:
            return await apple_music.play_playlist(match.group(1).strip())

    # Check for artist
    if any(word in query_lower for word in ["artist", "by", "songs by"]):
        match = re.search(r'(?:artist|by|songs by)[:\s]+(.+)', query, re.IGNORECASE)
        if match:
            return await _play_with_catalog(match.group(1).strip(), "artist")
        return await _play_with_catalog(query, "artist")

    # Check for album
    if "album" in query_lower:
        match = re.search(r'album[:\s]+(.+)', query, re.IGNORECASE)
        if match:
            return await _play_with_catalog(match.group(1).strip(), "album")

    # Default to track search
    return await _play_with_catalog(query, "track")


@llm.function_tool
async def music_pause() -> str:
    """Pause music playback."""
    return await apple_music.pause()


@llm.function_tool
async def music_stop() -> str:
    """Stop music playback completely."""
    return await apple_music.stop()


@llm.function_tool
async def music_next() -> str:
    """Skip to the next track."""
    return await apple_music.next_track()


@llm.function_tool
async def music_previous() -> str:
    """Go to the previous track."""
    return await apple_music.previous_track()


@llm.function_tool
async def music_current() -> str:
    """Get information about the currently playing track."""
    return await apple_music.get_current_track()


@llm.function_tool
async def music_volume(level: int) -> str:
    """
    Set the music volume.

    Args:
        level: Volume level from 0 to 100
    """
    if isinstance(level, str):
        try:
            level = int(level)
        except ValueError:
            return "Please provide a number between 0 and 100"
    return await apple_music.set_volume(level)


@llm.function_tool
async def music_shuffle(enabled: bool = True) -> str:
    """
    Enable or disable shuffle mode.

    Args:
        enabled: True to enable shuffle, False to disable
    """
    if isinstance(enabled, str):
        enabled = enabled.lower() in ('true', '1', 'yes', 'on')
    return await apple_music.shuffle(enabled)


@llm.function_tool
async def music_repeat(mode: str = "all") -> str:
    """
    Set repeat mode.

    Args:
        mode: 'off', 'one' (repeat current song), or 'all' (repeat playlist)
    """
    return await apple_music.repeat(mode)


@llm.function_tool
async def music_search(query: str, provider: str = "apple") -> str:
    """
    Search for music without playing.

    Args:
        query: What to search for
        provider: 'apple' or 'youtube'
    """
    if provider.lower() == "youtube":
        return youtube_music.search(query)
    return f"To play '{query}', say 'play {query}'"


def get_music_tools() -> list:
    """Get all music tools."""
    return [
        music_play,
        music_pause,
        music_stop,
        music_next,
        music_previous,
        music_current,
        music_volume,
        music_shuffle,
        music_repeat,
        music_search,
    ]
