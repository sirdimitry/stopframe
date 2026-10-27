from pathlib import Path
root = Path(defines['root'])
application = str(root / 'dist' / 'StopFrame Native (N).app')
files = [application]
symlinks = {'Applications': '/Applications'}
format = 'UDZO'
icon = str(root / 'assets' / 'branding' / 'StopFrame-N.icns')
background = str(root / 'assets' / 'branding' / 'dmg-background.png')
window_rect = ((180, 140), (720, 540))
icon_locations = {'StopFrame Native (N).app': (218, 230), 'Applications': (502, 230),
                  '.background.png': (1400, 900), '.background.tiff': (1400, 900),
                  '.VolumeIcon.icns': (1550, 900)}
icon_size = 80
text_size = 13
label_pos = 'bottom'
arrange_by = None
grid_offset = (0, 0)
scroll_position = (0, 0)
default_view = 'icon-view'
show_icon_preview = False
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
# Do not SetFile the signed app: FinderInfo invalidates strict signature checks.
hide_extensions = []
