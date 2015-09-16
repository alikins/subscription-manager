#
# Copyright (C) 2015  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import logging
import sys

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.common import FirstbootOnlySpokeMixIn
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.gui.utils import really_hide

log = logging.getLogger(__name__)

RHSM_PATH = "/usr/share/rhsm"
sys.path.append(RHSM_PATH)

from subscription_manager import ga_loader

# initial-setup only works with gtk version 3
ga_loader.init_ga(gtk_version="3")

from subscription_manager.ga import GObject as ga_GObject
from subscription_manager.ga import Gtk as ga_Gtk
from subscription_manager.gui import managergui
from subscription_manager.injectioninit import init_dep_injection
from subscription_manager import injection as inj
from subscription_manager.gui import registergui
from subscription_manager import utils
from subscription_manager.gui import utils as gui_utils

ga_GObject.threads_init()

__all__ = ["RHSMSpoke"]


class RHSMSpoke(FirstbootOnlySpokeMixIn, NormalSpoke):
    buildrObjects = ["RHSMSpokeWindow"]
    mainWidgetName = "RHSMSpokeWindow"
    uiFile = "rhsm_gui.ui"
    helpFile = "SubscriptionManagerSpoke.xml"
    category = SystemCategory
    icon = "face-cool-symbolic"
    title = "Subscription Manager"

    def __init__(self, data, storage, payload, instclass):
        NormalSpoke.__init__(self, date, storage, payload, instclass)
        self._done = False
        self._status_message = ""

    def initialize(self):
        NormalSpoke.initialize(self)
        self._done = False
        init_dep_injection()
        log.debug("self.data=%s", self.data)
        log.debug("type(self.data)=%s", type(self.data))

        facts = inj.require(inj.FACTS)

        backend = managergui.Backend()

        self.info = registergui.RegisterInfo()
        self.register_widget = registergui.RegisterWidget(backend, facts,
                                                          reg_info=self.info,
                                                          parent_window=self.main_window)

        self.register_box = self.builder.get_object("register_box")
        self.button_box = self.builder.get_object('navigation_button_box')
        self.proceed_button = self.builder.get_object('proceed_button')
        self.cancel_button = self.builder.get_object('cancel_button')

        self.register_box.pack_start(self.register_widget.register_widget,
                                     True, True, 0)

        # Hook up the nav buttons in the gui
        # TODO: add a 'start over'?
        self.proceed_button.connect('clicked', self._on_register_button_clicked)
        self.cancel_button.connect('clicked', self.cancel)

        # initial-setup will likely
        self.register_widget.connect('finished', self.finished)
        self.register_widget.connect('register-finished', self.register_finished)
        self.register_widget.connect('register-error', self._on_register_error)
        self.register_widget.connect('register-message', self._on_register_message)

        # update the 'next/register button on page change'
        self.register_widget.connect('notify::register-button-label',
                                       self._on_register_button_label_change)

        self.info.connect('notify::register-status', self._on_register_status_change)
        self.info.connect('notify::dry-run-result', self._on_dry_run_result_change)
        # We could watch dry-run-result

        self.register_box.show_all()
        self.register_widget.initialize()

    # handler for RegisterWidgets 'finished' signal
    def finished(self, obj):
        self._done = True
        really_hide(self.button_box)

    # If we completed registration, that's close enough to consider
    # completed.
    def register_finished(self, obj):
        self._done = True

    # Update gui widgets to reflect state of self.data
    # This could also be used to pre populate partial answers from a ks
    # or answer file
    def refresh(self):
        log.debug("data.addons.com_redhat_subscription_manager %s",
                  self.data.addons.com_redhat_subscription_manager)
        if self._data.serverurl:
            log.debug("serverurl=%s", self._data.serverurl)
            (hostname, port, prefix) = utils.parse_server_info(self._data.serverurl)
            self.info.set_property('hostname', hostname)
            self.info.set_property('port', port)
            self.info.set_property('prefix', prefix)

        if self._addon_data.username:
            self.info.set_property('username', self._addon_data.username)

        if self._addon_data.password:
            self.info.set_property('password', self._addon_data.password)

        if self._addon_data.org:
            self.info.set_property('owner_key', self._addon_data.org)

        if self._addon_data.activationkeys:
            self.info.set_property('activation_keys', self._addon_data.activationkeys)

        # TODO: support a ordered list of sla preferences?
        if self._addon_data.servicelevel:
            # NOTE: using the first sla in servicelevel only currently
            self.info.set_property('preferred_sla',
                                   self._addon_data.servicelevel[0])

        if self._addon_data.force:
            self.info.set_property('force', True)

        self.register_widget.populate_screens()

    # take info from the gui widgets and set into the self.data
    def apply(self):
        log.debug("apply")
        self.data.addons.com_redhat_subscription_manager.text = \
            "System is registered to Red Hat Subscription Management."

    # when the spoke is left, this can run anything that happens
    def execute(self):
        log.debug("execute")
        pass

    def cancel(self, button):
        # TODO: clear out settings and restart?
        # TODO: attempt to undo the REST api calls we've made?
        self.register_widget.set_initial_screen()
        self.register_widget.clear_screens()

    # A property indicating the spoke is ready to be visited. This
    # could depend on other modules or waiting for internal state to be setup.
    @property
    def ready(self):
        return True

    # Indicate if all the mandatory actions are completed
    @property
    def completed(self):
        # TODO: tie into register_widget.info.register-state
        return self._done

    # indicate if the module has to be completed before initial-setup is done.
    @property
    def mandatory(self):
        return False

    # A user facing string showing a summary of the status. This is displayed
    # under the spokes name on it's hub.
    @property
    def status(self):
        return self._status_message

    def _on_register_button_clicked(self, button):
        # unset any error info
        self.clear_info()

        self.register_widget.emit('proceed')

    # May merge error and message handling, but error can
    # include tracebacks and alter program flow...
    def _on_register_error(self, widget, msg, exc_info):
        if exc_info:
            formatted_msg = gui_utils.format_exception(exc_info, msg)
            self.set_error(formatted_msg)
        else:
            log.error(msg)
            self.set_error(msg)

    def _on_register_message(self, widget, msg, msg_type=None):
        # default to info.
        log.debug("_on_register_message msg=%s msg_type=%s", msg, msg_type)
        msg_type = msg_type or ga_Gtk.MessageType.INFO

        if msg_type == ga_Gtk.MessageType.INFO:
            log.debug("set_info")
            self.set_info(msg)
        elif msg_type == ga_Gtk.MessageType.WARNING:
            log.debug("set_warning")
            self.set_warning(msg)

    def _on_register_status_change(self, obj, value):
        self._status_message = obj.get_property('register-status')
        #self.status = self._status_message
        log.debug("register-status %s", self._status_message)

    def _on_dry_run_result_change(self, obj, value):
        dry_run_result = obj.get_property('register-status')
        log.debug("dry_run_result changed to: %s", dry_run_result)

    def _on_register_button_label_change(self, obj, value):
        register_label = obj.get_property('register-button-label')

        if register_label:
            self.proceed_button.set_label(register_label)
