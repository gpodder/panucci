#!/usr/bin/env python
# A resuming media player for Podcasts and Audiobooks
# Copyright (c) 2008-05-26 Thomas Perl <thpinfo.com>
#
# http://thpinfo.com/2008/panucci/
#
# based on http://pygstdocs.berlios.de/pygst-tutorial/seeking.html

import sys
import os
import thread
import time
import cPickle as pickle
import webbrowser

import gtk
import gobject
import pygst
pygst.require('0.10')
import gst

try:
    import gconf
except:
    # on the tablet, it's probably in "gnome"
    from gnome import gconf

import dbus
import dbus.service
import dbus.mainloop
import dbus.glib

# At the moment, we don't have gettext support, so
# make a dummy "_" function to passthrough the string
_ = lambda s: s


try:
    import hildon
except:
    pass

running_on_tablet = os.path.exists('/etc/osso_software_version')

about_name = 'Panucci'
about_text = _('Resuming audiobook and podcast player')
about_authors = ['Thomas Perl', 'Nick (nikosapi)', 'Matthew Taylor']
about_website = 'http://thpinfo.com/2008/panucci/'
donate_wishlist_url = 'http://www.amazon.de/gp/registry/2PD2MYGHE6857'
donate_device_url = 'http://maemo.gpodder.org/donate.html'

seek_time = 10
skip_time = 60


def open_link(d, url, data):
    webbrowser.open_new(url)
        
gtk.about_dialog_set_url_hook(open_link, None)


def find_image(filename):
    locations = ['./icons/', '../icons/', '/usr/share/panucci/', os.path.dirname(sys.argv[0])+'/../icons/']

    for location in locations:
        if os.path.exists(location+filename):
            return location+filename

    return None

gtk.icon_size_register('panucci-button', 32, 32)
def image(widget, filename, is_stock=False):
    widget.remove(widget.get_child())
    image = None
    if is_stock:
        image = gtk.image_new_from_stock(filename, gtk.icon_size_from_name('panucci-button'))
    else:
        filename = find_image(filename)
        if filename is not None:
            image = gtk.image_new_from_file(filename)

    if image is not None:
        if running_on_tablet:
            image.set_padding(20, 20)
        else:
            image.set_padding(5, 5)
        widget.add(image)
        image.show()

class PositionManager(object):
    def __init__(self, filename=None):
        if filename is None:
            filename = os.path.expanduser('~/.rmp-bookmarks')
        self.filename = filename

        try:
            # load the playback positions
            f = open(self.filename, 'rb')
            self.positions = pickle.load(f)
            f.close()
        except:
            # let's start out with a new dict
            self.positions = {}

    def set_position(self, url, position):
        if not url in self.positions:
            self.positions[url] = {}

        self.positions[url]['position'] = position

    def get_position(self, url):
        if url in self.positions and 'position' in self.positions[url]:
            return self.positions[url]['position']
        else:
            return 0

    def set_bookmarks(self, url, bookmarks):
        if not url in self.positions:
            self.positions[url] = {}

        self.positions[url]['bookmarks'] = bookmarks

    def get_bookmarks(self, url):
        if url in self.positions and 'bookmarks' in self.positions[url]:
            return self.positions[url]['bookmarks']
        else:
            return []

    def save(self):
        # save the playback position dict
        f = open(self.filename, 'wb')
        pickle.dump(self.positions, f)
        f.close()

pm = PositionManager()

class BookmarksWindow(gtk.Window):
    def __init__(self, main):
        self.main = main
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title('Bookmarks')
        self.set_modal(True)
        self.set_default_size(400, 300)
        self.set_border_width(10)
        self.vbox = gtk.VBox()
        self.vbox.set_spacing(5)
        self.treeview = gtk.TreeView()
        self.treeview.set_headers_visible(True)
        self.model = gtk.ListStore(gobject.TYPE_STRING,
            gobject.TYPE_STRING, gobject.TYPE_UINT64)
        self.treeview.set_model(self.model)

        ncol = gtk.TreeViewColumn('Name')
        ncell = gtk.CellRendererText()
        ncell.set_property('editable', True)
        ncell.connect('edited', self.label_edited)
        ncol.pack_start(ncell)
        ncol.add_attribute(ncell, 'text', 0)

        tcol = gtk.TreeViewColumn('Time')
        tcell = gtk.CellRendererText()
        tcol.pack_start(tcell)
        tcol.add_attribute(tcell, 'text', 1)

        self.treeview.append_column(ncol)
        self.treeview.append_column(tcol)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.treeview)
        self.vbox.add(sw)
        self.hbox = gtk.HButtonBox()
        self.add_button = gtk.Button(gtk.STOCK_ADD)
        self.add_button.set_use_stock(True)
        self.add_button.connect('clicked', self.add_bookmark)
        self.hbox.pack_start(self.add_button)
        self.remove_button = gtk.Button(gtk.STOCK_REMOVE)
        self.remove_button.set_use_stock(True)
        self.remove_button.connect('clicked', self.remove_bookmark)
        self.hbox.pack_start(self.remove_button)
        self.jump_button = gtk.Button(gtk.STOCK_JUMP_TO)
        self.jump_button.set_use_stock(True)
        self.jump_button.connect('clicked', self.jump_bookmark)
        self.hbox.pack_start(self.jump_button)
        self.close_button = gtk.Button(gtk.STOCK_CLOSE)
        self.close_button.set_use_stock(True)
        self.close_button.connect('clicked', self.close)
        self.hbox.pack_start(self.close_button)
        self.vbox.pack_start(self.hbox, False, True)
        self.add(self.vbox)
        for label, pos in pm.get_bookmarks(self.main.filename):
            self.add_bookmark(label=label, pos=pos)
        self.show_all()

    def close(self, w):
        bookmarks = []
        for row in self.model:
            bookmarks.append((row[0], row[2]))
        pm.set_bookmarks(self.main.filename, bookmarks)
        self.destroy()

    def label_edited(self, cellrenderer, path, new_text):
        self.model.set_value(self.model.get_iter(path), 0, new_text)

    def add_bookmark(self, w=None, label=None, pos=None):
        (text, position) = self.main.get_position(pos)
        if label is None:
            label = text
        self.model.append([label, text, position])
    
    def remove_bookmark(self, w):
        selection = self.treeview.get_selection()
        (model, iter) = selection.get_selected()
        if iter is not None:
            model.remove(iter)

    def jump_bookmark(self, w):
        selection = self.treeview.get_selection()
        (model, iter) = selection.get_selected()
        if iter is not None:
            pos = model.get_value(iter, 2)
            self.main.do_seek(pos)

class GTK_Main(dbus.service.Object):
	
    def save_position(self):
        try:
            (pos, format) = self.player.query_position(self.time_format, None)
            pm.set_position(self.filename, pos)
        except:
            pass

    def get_position(self, pos=None):
        if pos is None:
            try:
                pos = self.player.query_position(self.time_format, None)[0]
            except:
                pos = 0
        text = self.convert_ns(pos)
        return (text, pos)

    def destroy(self, widget):
        self.save_position()
        if running_on_tablet:
            vol = self.volume.get_level()
        else:
            vol = int(self.volume.get_value()*100)
        pm.set_position( 'volume', vol )
        gtk.main_quit()

    def gconf_key_changed(self, client, connection_id, entry, args):
        print 'gconf key %s changed: %s' % (entry.get_key(), entry.get_value())
   
    def handle_headset_button(self, event, button):
        if event == 'ButtonPressed' and button == 'phone':
            self.start_stop(self.button)

    def __init__(self, bus_name, filename=None):
        dbus.service.Object.__init__(self, object_path="/player",
            bus_name=bus_name)

        self.filename = filename
        self.make_main_window()
        self.has_coverart = False

        self.gconf_client = gconf.client_get_default()
        self.gconf_client.add_dir('/apps/panucci', gconf.CLIENT_PRELOAD_NONE)
        self.gconf_client.notify_add('/apps/panucci', self.gconf_key_changed)

        if running_on_tablet:
            # Enable play/pause with headset button
            system_bus = dbus.SystemBus()
            headset_button = system_bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/devices/platform_retu_headset_logicaldev_input')
            headset_device = dbus.Interface(headset_button, 'org.freedesktop.Hal.Device')
            headset_device.connect_to_signal('Condition', self.handle_headset_button)

        self.want_to_seek = False
        self.player = gst.element_factory_make('playbin', 'player')

        vol = pm.get_position('volume')
        if vol == 0: vol = 20
        if running_on_tablet:
            self.volume.set_level(vol)
        else:
            self.volume.set_value(vol/100.0)

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        self.time_format = gst.Format(gst.FORMAT_TIME)
        if self.filename is not None:
            gobject.timeout_add(200, self.start_playback)

    def make_main_window(self):
        import pango
        		
        if running_on_tablet:
            self.app = hildon.Program()
            window = hildon.Window()
            self.app.add_window(window)
        else:
            window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        
        window.set_title('Panucci')
        window.set_default_size(400, -1)
        window.set_border_width(0)
        window.connect("destroy", self.destroy)
        self.main_window = window
        
                
        if running_on_tablet:
            window.set_menu(self.create_menu())
        else:
            menu_vbox = gtk.VBox()
            menu_vbox.set_spacing(0)
            window.add(menu_vbox)
            menu_bar = gtk.MenuBar()
            root_menu = gtk.MenuItem('Panucci')
            root_menu.set_submenu(self.create_menu())
            menu_bar.append(root_menu)
            menu_vbox.pack_start(menu_bar, False, False, 0)
            menu_bar.show()

        main_hbox = gtk.HBox()
        main_hbox.set_spacing(6)
        if running_on_tablet:
            window.add(main_hbox)
        else:
            menu_vbox.pack_end(main_hbox, True, True, 6)

        main_vbox = gtk.VBox()
        main_vbox.set_spacing(6)
        # add a vbox to the main_hbox
        main_hbox.pack_start(main_vbox, True, True)

        # a hbox to hold the cover art and metadata vbox
        metadata_hbox = gtk.HBox()
        metadata_hbox.set_spacing(6)
        main_vbox.pack_start(metadata_hbox, True, False)

        self.cover_art = gtk.Image()
        metadata_hbox.pack_start( self.cover_art, False, False )

        # vbox to hold metadata
        metadata_vbox = gtk.VBox()
        metadata_vbox.set_spacing(8)
        empty_label = gtk.Label()
        metadata_vbox.pack_start(empty_label, True, True)
        self.artist_label = gtk.Label('')
        self.artist_label.set_ellipsize(pango.ELLIPSIZE_END)
        metadata_vbox.pack_start(self.artist_label, False, False)
        self.album_label = gtk.Label('')
        self.album_label.set_ellipsize(pango.ELLIPSIZE_END)
        metadata_vbox.pack_start(self.album_label, False, False)
        self.title_label = gtk.Label('')
        self.title_label.set_ellipsize(pango.ELLIPSIZE_END)
        metadata_vbox.pack_start(self.title_label, False, False)
        empty_label = gtk.Label()
        metadata_vbox.pack_start(empty_label, True, True)
        metadata_hbox.pack_start( metadata_vbox, True, True )

        # make the button box
        buttonbox = gtk.HBox()
        self.rrewind_button = gtk.Button('')
        image(self.rrewind_button, 'media-skip-backward.png')
        self.rrewind_button.connect("clicked", self.rewind_callback)
        buttonbox.add(self.rrewind_button)
        self.rewind_button = gtk.Button('')
        image(self.rewind_button, 'media-seek-backward.png')
        self.rewind_button.connect("clicked", self.rewind_callback)
        buttonbox.add(self.rewind_button)
        self.playing = False
        self.button = gtk.Button('')
        image(self.button, gtk.STOCK_OPEN, True)
        self.button.connect("clicked", self.start_stop)
        buttonbox.add(self.button)
        self.forward_button = gtk.Button('')
        image(self.forward_button, 'media-seek-forward.png')
        self.forward_button.connect("clicked", self.forward_callback)
        buttonbox.add(self.forward_button)
        self.fforward_button = gtk.Button('')
        image(self.fforward_button, 'media-skip-forward.png')
        self.fforward_button.connect("clicked", self.forward_callback)
        buttonbox.add(self.fforward_button)
        self.bookmarks_button = gtk.Button('')
        image(self.bookmarks_button, 'bookmark-new.png')
        self.bookmarks_button.connect("clicked", self.bookmarks_callback)
        buttonbox.add(self.bookmarks_button)
        self.set_controls_sensitivity(False)

        if running_on_tablet:
            self.volume = hildon.VVolumebar()
            self.volume.set_property('can-focus', False)
            self.volume.set_property('has-mute', False)
            self.volume.connect('level_changed', self.volume_changed2)
            self.volume.connect('mute_toggled', self.mute_toggled)
            window.connect('key-press-event', self.on_key_press)
            main_hbox.pack_start(self.volume, False, True)
            # Disable focus for all widgets, so we can use the cursor
            # keys + enter to directly control our media player, which
            # is handled by "key-press-event"
            for w in (self.rrewind_button, self.rewind_button, self.button,
                    self.forward_button, self.fforward_button, self.bookmarks_button,
                    self.volume):
                w.unset_flags(gtk.CAN_FOCUS)
        else:
            self.volume = gtk.VolumeButton()
            self.volume.connect('value-changed', self.volume_changed)
            buttonbox.add(self.volume)

        self.progress = gtk.ProgressBar()
        main_vbox.pack_start(self.progress, False, False)
        main_vbox.pack_start(buttonbox, False, False)
        self.progress.set_text("00:00 / 00:00")

        window.show_all()

    def create_menu(self):
        menu = gtk.Menu()
        menu_donate_sub = gtk.Menu()
        
        menu_open = gtk.ImageMenuItem(gtk.STOCK_OPEN)
        #haven't quite worked this part out yet - matt
        #menu_open.connect("activate", self.file_open, self.main_window)
        menu_bookmarks = gtk.MenuItem(_('Bookmarks'))
        menu_bookmarks.connect('activate', self.bookmarks_callback)
        
        menu_donate = gtk.MenuItem(_('Donate'))

        menu_donate_device = gtk.MenuItem(_('Developer device'))
        menu_donate_device.connect("activate", lambda w: webbrowser.open_new(donate_device_url))
        
        menu_donate_wishlist = gtk.MenuItem(_('Amazon Wishlist'))
        menu_donate_wishlist.connect("activate", lambda w: webbrowser.open_new(donate_wishlist_url))

        menu_about = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
        menu_about.connect("activate", self.show_about, self.main_window)

        menu_quit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        menu_quit.connect("activate", self.destroy)
        
        menu.append(menu_open)
        menu.append(gtk.SeparatorMenuItem())
        menu.append(menu_bookmarks)
        menu.append(gtk.SeparatorMenuItem())

        menu.append(menu_donate)
        menu_donate_sub.append(menu_donate_device)
        menu_donate_sub.append(menu_donate_wishlist)
        menu_donate.set_submenu(menu_donate_sub)

        menu.append(menu_about)

        menu.append(gtk.SeparatorMenuItem())
        menu.append(menu_quit)

        return menu

    def show_about(self, w, win):
        dialog = gtk.AboutDialog()
        dialog.set_website(about_website)
        dialog.set_website_label(about_website)
        dialog.set_name(about_name)
        dialog.set_authors(about_authors)
        dialog.set_comments(about_text)
        dialog.run()
        dialog.destroy()
        
    @dbus.service.method('org.panucci.interface')
    def show_main_window(self):
        self.main_window.present()

    def set_controls_sensitivity(self, sensitive):
        self.forward_button.set_sensitive(sensitive)
        self.rewind_button.set_sensitive(sensitive)
        self.fforward_button.set_sensitive(sensitive)
        self.rrewind_button.set_sensitive(sensitive)

    def on_key_press(self, widget, event):
        if event.keyval == gtk.keysyms.F7: #plus
            self.volume.set_level( min( 100, self.volume.get_level() + 10 ))
        elif event.keyval == gtk.keysyms.F8: #minus
            self.volume.set_level( max( 0, self.volume.get_level() - 10 ))
        elif event.keyval == gtk.keysyms.Left: # seek back
            self.rewind_callback(self.rewind_button)
        elif event.keyval == gtk.keysyms.Right: # seek forward
            self.forward_callback(self.forward_button)
        elif event.keyval == gtk.keysyms.Return: # play/pause
            self.start_stop(self.button)

    def volume_changed(self, widget, new_value=8.0):
        self.player.set_property('volume', float(new_value))
        return True

    def volume_changed2(self, widget):
        self.player.set_property('volume', float(widget.get_level()/100.*10.))
        return True

    def mute_toggled(self, widget):
        if widget.get_mute():
            self.player.set_property('volume', float(0))
        else:
            self.player.set_property('volume', float(widget.get_level()/100.*10.))

    @dbus.service.method('org.panucci.interface', in_signature='s')
    def play_file(self, filename):
        if self.playing:
            self.start_stop(None)
        self.filename = filename
        self.has_coverart = False
        self.start_playback()

    def start_playback(self):
        self.start_stop(None)
        self.set_controls_sensitivity(True)
        self.title_label.hide()
        self.artist_label.hide()
        self.album_label.hide()
        self.cover_art.hide()
        return False
        
    def start_stop(self, w):
        self.playing = not self.playing
        if self.playing:
            self.want_to_seek = True
            if self.filename is None or not os.path.exists(self.filename):
                if running_on_tablet:
                    dlg = hildon.FileChooserDialog(self.main_window,
                        gtk.FILE_CHOOSER_ACTION_OPEN)
                else:
                    dlg = gtk.FileChooserDialog(_('Select podcast or audiobook'),
                        None, gtk.FILE_CHOOSER_ACTION_OPEN, ((gtk.STOCK_CANCEL,
                        gtk.RESPONSE_REJECT, gtk.STOCK_MEDIA_PLAY, gtk.RESPONSE_OK)))

                current_folder = self.gconf_client.get_string('/apps/panucci/last_folder')
                if current_folder is not None and os.path.isdir(current_folder):
                    dlg.set_current_folder(current_folder)

                if dlg.run() == gtk.RESPONSE_OK:
                    self.filename = dlg.get_filename()
                    self.gconf_client.set_string('/apps/panucci/last_folder', dlg.get_current_folder())
                    dlg.destroy()
                else:
                    dlg.destroy()
                    return
            self.filename = os.path.abspath(self.filename)
            self.player.set_property('uri', 'file://'+self.filename)
            self.player.set_state(gst.STATE_PLAYING)
            image(self.button, 'media-playback-pause.png')
            self.play_thread_id = thread.start_new_thread(self.play_thread, ())
        else:
            self.want_to_seek = False
            self.save_position()
            self.play_thread_id = None
            self.player.set_state(gst.STATE_NULL)
            image(self.button, 'media-playback-start.png')

    def do_seek(self, seek_ns=None):
        if seek_ns is None:
            seek_ns = pm.get_position(self.filename)
        if seek_ns != 0:
            self.player.seek_simple(self.time_format, gst.SEEK_FLAG_FLUSH, seek_ns)
        self.want_to_seek = False

    def play_thread(self):
        play_thread_id = self.play_thread_id
        gtk.gdk.threads_enter()
        self.progress.set_text("00:00 / 00:00")
        gtk.gdk.threads_leave()

        while play_thread_id == self.play_thread_id:
            try:
                time.sleep(0.2)
                dur_int = self.player.query_duration(self.time_format, None)[0]
                dur_str = self.convert_ns(dur_int)
                gtk.gdk.threads_enter()
                self.progress.set_text("00:00 / " + dur_str)
                self.progress.set_fraction(0)
                gtk.gdk.threads_leave()
                break
            except:
                pass
                
        time.sleep(0.2)
        while play_thread_id == self.play_thread_id:
            pos_int = self.player.query_position(self.time_format, None)[0]
            pos_str = self.convert_ns(pos_int)
            if play_thread_id == self.play_thread_id and pos_str != '00:00':
                gtk.gdk.threads_enter()
                self.progress.set_fraction(float(pos_int)/float(dur_int+1))
                self.progress.set_text('%s / %s' % ( pos_str, 
                    self.convert_ns(dur_int)))
                gtk.gdk.threads_leave()
            time.sleep(1)

            
    def on_message(self, bus, message):
        t = message.type

        if t == gst.MESSAGE_EOS:
            self.play_thread_id = None
            self.player.set_state(gst.STATE_NULL)
            image(self.button, 'media-playback-pause.png')
            self.progress.set_text("00:00 / 00:00")
            pm.set_position(self.filename, 0)

        elif t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.play_thread_id = None
            self.player.set_state(gst.STATE_NULL)
            image(self.button, 'media-playback-start.png')
            self.progress.set_text("00:00 / 00:00")

        elif t == gst.MESSAGE_STATE_CHANGED:
            if ( message.src == self.player and
                message.structure['new-state'] == gst.STATE_PLAYING ):

                if self.want_to_seek:
                    self.do_seek()
                else:
                    self.set_controls_sensitivity(True)

        elif t == gst.MESSAGE_TAG:
            keys = message.parse_tag().keys()
            tags = dict([ (key, message.structure[key]) for key in keys ])
            gtk.gdk.threads_enter()
            self.set_metadata( tags )
            gtk.gdk.threads_leave()

    def set_coverart( self, pixbuf ):
        self.cover_art.set_from_pixbuf(pixbuf)
        self.cover_art.show()
        self.has_coverart = True

    def set_metadata( self, tag_message ):
        tags = { 'title': self.title_label, 'artist': self.artist_label,
                 'album': self.album_label }
 
        cover_names = [ 'cover', 'cover.jpg', 'cover.png' ]

        if running_on_tablet:
            size = [240, 240]
        else:
            size = [130, 130]

        if tag_message.has_key('image') and not self.has_coverart:
            value = tag_message['image']
            if isinstance( value, list ):
                value = value[0]

            pbl = gtk.gdk.PixbufLoader()
            try:
                pbl.write(value.data)
                pbl.close()
                pixbuf = pbl.get_pixbuf().scale_simple(
                    size[0], size[1], gtk.gdk.INTERP_BILINEAR )
                self.set_coverart(pixbuf)
            except:
                #traceback.print_exc(file=sys.stdout)
                pbl.close()

        if not self.has_coverart and self.filename is not None:
            for cover in cover_names:
                c = os.path.join( os.path.dirname( self.filename ), cover )
                if os.path.isfile(c):
                    try:
                        pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(c, *size)
                        self.set_coverart(pixbuf)
                    except: pass
                    break

        tag_vals = dict([ (i,'') for i in tags.keys()])
        for tag,value in tag_message.iteritems():
            if tags.has_key(tag):
                tags[tag].set_markup('<big>'+value+'</big>')
                tag_vals[tag] = value
                tags[tag].set_alignment( 0.5*int(not self.has_coverart), 0.5)
                tags[tag].show()
            if tag == 'title':
                if running_on_tablet:
                    self.main_window.set_title(value)
                else:
                    self.main_window.set_title('Panucci - ' + value)

        for tag_val in [ tag_vals['artist'].lower(), tag_vals['album'].lower() ]:
            if not tag_vals['title'].strip():
                break
            if tag_vals['title'].lower().startswith(tag_val):
                t = tag_vals['title'][len(tag_val):].lstrip()
                t = t.lstrip('-').lstrip(':').lstrip()
                tags['title'].set_markup('<span size="x-large">'+t+'</span>')
                break

    def demuxer_callback(self, demuxer, pad):
        adec_pad = self.audio_decoder.get_pad("sink")
        pad.link(adec_pad)
    
    def rewind_callback(self, w):
        if not w.get_property('sensitive'):
            return

        global skip_time
        global seek_time
        if w == self.rewind_button:
            seconds = seek_time
        else:
            seconds = skip_time
        self.set_controls_sensitivity(False)
        pos_int = self.player.query_position(self.time_format, None)[0]
        seek_ns = max(0, pos_int - (seconds * 1000000000L))
        self.player.seek_simple(self.time_format, gst.SEEK_FLAG_FLUSH, seek_ns)

    def bookmarks_callback(self, w):    
        BookmarksWindow(self)

    def forward_callback(self, w):
        if not w.get_property('sensitive'):
            return

        global skip_time
        global seek_time
        if w == self.forward_button:
            seconds = seek_time
        else:
            seconds = skip_time
        self.set_controls_sensitivity(False)
        pos_int = self.player.query_position(self.time_format, None)[0]
        seek_ns = pos_int + (seconds * 1000000000L)
        self.player.seek_simple(self.time_format, gst.SEEK_FLAG_FLUSH, seek_ns)
    
    def convert_ns(self, time_int):
        time_int = time_int / 1000000000
        time_str = ""
        if time_int >= 3600:
            _hours = time_int / 3600
            time_int = time_int - (_hours * 3600)
            time_str = str(_hours) + ":"
        if time_int >= 600:
            _mins = time_int / 60
            time_int = time_int - (_mins * 60)
            time_str = time_str + str(_mins) + ":"
        elif time_int >= 60:
            _mins = time_int / 60
            time_int = time_int - (_mins * 60)
            time_str = time_str + "0" + str(_mins) + ":"
        else:
            time_str = time_str + "00:"
        if time_int > 9:
            time_str = time_str + str(time_int)
        else:
            time_str = time_str + "0" + str(time_int)
            
        return time_str


def run(filename=None):
    session_bus = dbus.SessionBus(mainloop=dbus.glib.DBusGMainLoop())
    bus_name = dbus.service.BusName('org.panucci', bus=session_bus)    
    GTK_Main(bus_name, filename)
    gtk.gdk.threads_init()
    gtk.main()
    # save position manager data
    pm.save()

if __name__ == '__main__':
    print 'WARNING: Use "panucci" to run this application.'
    print 'Exiting...'

