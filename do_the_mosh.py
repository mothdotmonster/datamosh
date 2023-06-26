#!/usr/bin/env python3

import sys, os, argparse, pprint
from ffmpeg import FFmpeg, Progress

pp = pprint.PrettyPrinter(compact=True)

video_start = 0
effect_start = 3
effect_end   = 6
video_end = 60
repeat_frames = 15
fps = 30

output_directory = 'moshed_videos'

# this makes sure the video file exists. It is used below in the 'input_video' argparse
def quit_if_no_video_file(video_file):
	if not os.path.isfile(video_file):
		raise argparse.ArgumentTypeError("Couldn't find {}. You might want to check the file name??".format(video_file))
	else:
		return(video_file)

# make sure the output directory exists
def confirm_output_directory(output_directory):
	if not os.path.exists(output_directory): os.mkdir(output_directory)

	return(output_directory)

# this makes the options available at the command line for ease of use

# 'parser' is the name of our new parser which checks the variables we give it to make sure they will probably work 
# or else offer helpful errors and tips to the user at the command line
parser = argparse.ArgumentParser() 

parser.add_argument('input_video', type=quit_if_no_video_file, help="File to be moshed")
parser.add_argument('--video_start',        default = video_start,        type=float, help="Time the video starts on the original footage's timeline. Trims preceding footage.")
parser.add_argument('--video_end',    	  default = video_end,          type=float, help="Time on the original footage's time when it is trimmed.")
parser.add_argument('--effect_start', default = effect_start, type=float, help="Time the effect starts on the trimmed footage's timeline. The output video can be much longer.")
parser.add_argument('--effect_end',   default = effect_end,   type=float, help="Time the effect ends on the trimmed footage's timeline.")
parser.add_argument('--repeat_frames',  default = repeat_frames,  type=int,   help="If this is set to 0 the result will only contain i-frames. Possibly only a single i-frame.")
parser.add_argument('--fps',              default = fps,              type=int,   help="The number of frames per second the initial video is converted to before moshing.")
parser.add_argument('--output_dir',       default = output_directory, type=confirm_output_directory, help="Output directory")

# this makes sure the local variables are up to date after all the argparsing
locals().update( parser.parse_args().__dict__.items() )

end_effect_hold = effect_end - effect_start
effect_start = effect_start - video_start

effect_end = effect_start + end_effect_hold

print('start time from original video: ',str(video_start))
print('end time from original video: ',str(video_end))
print('mosh effect applied at: ',str(effect_start))
print('mosh effect stops being applied at: ',str(effect_end))

if effect_start > effect_end:
	print("No moshing will occur because --effect_start begins after --effect_end")
	sys.exit()

# where we make new file names
# basename seperates the file name from the directory it's in so /home/user/you/video.mp4 becomes video.mp4
# splitext short for "split extension" splits video.mp4 into a list ['video','.mp4'] and [0] returns 'video' to file_name
file_name = os.path.splitext( os.path.basename(input_video) )[0]
# path.join pushes the directory and file name together and makes sure there's a / between them
input_avi =  os.path.join(output_dir, 'datamoshing_input.avi')			# must be an AVI so i-frames can be located in binary file
output_avi = os.path.join(output_dir, 'datamoshing_output.avi')
# {} is where 'file_name' is put when making the 'output_video' variable
output_video = os.path.join(output_dir, 'moshed_{}.mp4'.format(file_name))		# this ensures we won't over-write your original video


# THIS IS WHERE THE MAGIC HAPPENS

convertToAVI = (
		FFmpeg()
		.option("y")
		.input(input_video)
		.output(
			input_avi,
			crf = 0,
			pix_fmt = "yuv420p",
			r = fps,
			ss = video_start,
			to = video_end,
			force_key_frames = effect_start
		)
)

@convertToAVI.on("progress")
def on_progress(progress: Progress):
		pp.pprint(progress)

convertToAVI.execute()

# open up the new files so we can read and write bytes to them
in_file  = open(input_avi,  'rb')
out_file = open(output_avi, 'wb')

# because we used 'rb' above when the file is read the output is in byte format instead of Unicode strings
in_file_bytes = in_file.read()

# 0x30306463 which is ASCII 00dc signals the end of a frame. '0x' is a common way to say that a number is in hexidecimal format.
frames = in_file_bytes.split(bytes.fromhex('30306463'))

# 0x0001B0 signals the beginning of an i-frame. Additional info: 0x0001B6 signals a p-frame
iframe = bytes.fromhex('0001B0')

# We want at least one i-frame before the glitching starts
i_frame_yet = False

for index, frame in enumerate(frames):

	if  i_frame_yet == False or index < int(effect_start * fps) or index > int(effect_end * fps):
		# the split above removed the end of frame signal so we put it back in
		out_file.write(frame + bytes.fromhex('30306463'))

		# found an i-frame, let the glitching begin
		if frame[5:8] == iframe: i_frame_yet = True

	else:
		# while we're moshing we're repeating p-frames and multiplying i-frames
		if frame[5:8] != iframe:
			# this repeats the p-frame x times
			for i in range(repeat_frames):
				out_file.write(frame + bytes.fromhex('30306463'))

in_file.close()
out_file.close()


makeOutput = (
		FFmpeg()
		.option("y")
		.input(output_avi)
		.output(
			output_video,
			r = fps,
		)
)

@makeOutput.on("progress")
def on_progress(progress: Progress):
		pp.pprint(progress)

makeOutput.execute()


# gets rid of the in-between files so they're not crudding up your system
os.remove(input_avi)
os.remove(output_avi)
