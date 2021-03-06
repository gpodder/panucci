
import QtQuick 1.1

Item {
    id: playlistItemInfoArea
    signal close
    property variant metadata: {"artist":"","title":"","length":"","album":"","path":""}
    onClose: { playlistItemInfoFlick.contentX = 0
               playlistItemInfoFlick.contentY = 0
    }
    MouseArea {
        anchors.fill: parent
        onClicked: playlistItemInfoArea.close()
    }
    Rectangle {
        color: themeController.background
        anchors.fill: parent
        opacity: .9
    }
    Text {
        text: info_header_str
        y: config.font_size
        anchors.horizontalCenter: parent.horizontalCenter
        font.pixelSize: config.font_size * 1.5
        color: themeController.foreground
    }
    Flickable {
        id: playlistItemInfoFlick
        width: root.width
        height: root.height - config.font_size - 3.5
        x: 0
        y: config.font_size * 3.5
        //contentWidth: root.width * 2
        contentWidth: leftColumn.width + rightColumn.width + (config.font_size * 2.5)
        clip: true

        MouseArea {
        anchors.fill: parent
        onClicked: playlistItemInfoArea.close()
        }
        Column {
            id: leftColumn
            x: config.font_size
            y: 0
            spacing: config.font_size / 2

            Text {
                text: info_title_str
                anchors.right: parent.right
                font.pixelSize: config.font_size
                color: themeController.foreground
            }
            Text {
                text: info_length_str
                anchors.right: parent.right
                font.pixelSize: config.font_size
                color: themeController.foreground
            }
            Text {
                text: info_artist_str
                anchors.right: parent.right
                font.pixelSize: config.font_size
                color: themeController.foreground
            }
            Text {
                text: info_album_str
                anchors.right: parent.right
                font.pixelSize: config.font_size
                color: themeController.foreground
            }
            Text {
                text: info_filepath_str
                anchors.right: parent.right
                font.pixelSize: config.font_size
                color: themeController.foreground
            }
        }
        Column {
            id: rightColumn
            spacing: config.font_size / 2
            anchors {
                top: leftColumn.top
                left: leftColumn.right
                leftMargin: config.font_size / 2
            }
            Text {
                text: playlistItemInfoArea.metadata["title"]
                font.pixelSize: config.font_size
                color: themeController.foreground
            }
            Text {
                text: playlistItemInfoArea.metadata["length"]
                font.pixelSize: config.font_size
                color: themeController.foreground
            }
            Text {
                text: playlistItemInfoArea.metadata["artist"]
                font.pixelSize: config.font_size
                color: themeController.foreground
            }
            Text {
                text: playlistItemInfoArea.metadata["album"]
                font.pixelSize: config.font_size
                color: themeController.foreground
            }
            Text {
                text: playlistItemInfoArea.metadata["path"]
                font.pixelSize: config.font_size
                color: themeController.foreground
            }
        }
    }
}
