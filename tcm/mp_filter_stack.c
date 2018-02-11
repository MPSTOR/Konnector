/*
 * Copyright 2014, Red Hat, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
*/

/*
 * Example code to demonstrate how a TCMU handler might work.
 *
 * Using the example of backing a device by a file to demonstrate:
 *
 * 1) Registering with tcmu-runner
 * 2) Parsing the handler-specific config string as needed for setup
 * 3) Opening resources as needed
 * 4) Handling SCSI commands and using the handler API
 */

#define _GNU_SOURCE
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <endian.h>
#include <scsi/scsi.h>
#include <dlfcn.h> //added by DC to enable run-time linking of filter so objects - DC
#include "tcmu-runner.h"

//below defines default path to compiled so filter objects - DC
#ifndef DEFAULT_FILTER_PATH
#define DEFAULT_FILTER_PATH "/usr/lib64/tcmu-filters"
#endif

char *default_filter_path = DEFAULT_FILTER_PATH;

struct file_state {
	int fd;
	uint64_t num_lbas;
	uint32_t block_size;
};

char line[256];



void debug_write (char * str)
{
 	int fd = open ("/tmp/debugdedup", O_WRONLY|O_APPEND|O_CREAT);  // Not the best performant
	write (fd, str, strlen(str));
	close(fd);
}

void apply_read_throttle_mbs( struct tcmu_device *dev,  char* throttle  )
{
	char* config = dev->cfgstring;
	char* throttle_amt = strchr(throttle, '-') + 1;
	char* throttle_cmd;
	char* device;
	char throttle_out[32];
	const unsigned int cnv_mb = 1048576;
	unsigned int throttle_val_bps=0;
	int string_mem;

        device = strrchr(config,'/') + 1;
        dbgp("Device  %s \n", device ) ;
        dbgp("Read throttle value  %s \n", throttle_amt );
	throttle_val_bps=atoi(throttle_amt) * cnv_mb;//throttle value is passed as MB/s in a string - convert to int apply conversion factor to bytes per second - DC
	//itoa(throttle_val_bps, throttle_out, 10);
	sprintf(throttle_out,"%d",throttle_val_bps);//NB, it appears that itoa is not supported so vanilla sprintf instead to convert back to string - DC
	//below builds final string that is sent to BASH as a cgroup based throttling command - DC
	string_mem = asprintf(&throttle_cmd, "echo \"$(cat \"/sys/block/%s\"/dev) %s\" >> /sys/fs/cgroup/blkio/blkio.throttle.read_bps_device", device, throttle_out);

	if (string_mem == -1) {
                errp("ENOMEM\n");
                goto err;
        }

        system(throttle_cmd);

        free(throttle_cmd);

err:
	return;
}

void apply_read_throttle_iops( struct tcmu_device *dev,  char* throttle  )
{
        char* config = dev->cfgstring;
        char* throttle_amt = strchr(throttle, '-') + 1;
        char* throttle_cmd;
        char* device;
        char throttle_out[32];
        unsigned int throttle_val_iops=0;
        int string_mem;

        device = strrchr(config,'/') + 1;
        dbgp("Device  %s \n", device ) ;
        dbgp("Read throttle value  %s \n", throttle_amt );
        throttle_val_iops=atoi(throttle_amt);
        //itoa(throttle_val_bps, throttle_out, 10);
        sprintf(throttle_out,"%d",throttle_val_iops);//NB, it appears that itoa is not supported so vanilla sprintf instead to convert back to string - DC
        //below builds final string that is sent to BASH as a cgroup based throttling command - DC
        string_mem = asprintf(&throttle_cmd, "echo \"$(cat \"/sys/block/%s\"/dev) %s\" >> /sys/fs/cgroup/blkio/blkio.throttle.read_iops_device", device, throttle_out);

        if (string_mem == -1) {
                errp("ENOMEM\n");
                goto err;
        }

        system(throttle_cmd);

        free(throttle_cmd);

err:
        return;
}

void apply_write_throttle_mbs( struct tcmu_device *dev,  char* throttle  )
{
        char* config = dev->cfgstring;
        char* throttle_amt = strchr(throttle, '-') + 1;
        char* throttle_cmd;
        char* device;
        char throttle_out[32];
        const unsigned int cnv_mb = 1048576;
        unsigned int throttle_val_bps=0;
        int string_mem;

        device = strrchr(config,'/') + 1;
        dbgp("Device  %s \n", device ) ;
        dbgp("Write throttle value  %s \n", throttle_amt );
        throttle_val_bps=atoi(throttle_amt) * cnv_mb;//throttle value is passed as MB/s in a string convert to int apply conversion factor to bytes per second -DC
        //itoa(throttle_val_bps, throttle_out, 10);
        sprintf(throttle_out,"%d",throttle_val_bps);//NB, it appears that itoa is not supported so vanilla sprintf instead to convert back to string - DC
        //below builds final string that is sent to BASH as a cgroup based throttling command - DC
        string_mem = asprintf(&throttle_cmd, "echo \"$(cat \"/sys/block/%s\"/dev) %s\" >> /sys/fs/cgroup/blkio/blkio.throttle.write_bps_device", device, throttle_out);

        if (string_mem == -1) {
                errp("ENOMEM\n");
                goto err;
        }

        system( throttle_cmd );

        free(throttle_cmd);

err:
        return;
}

void apply_write_throttle_iops( struct tcmu_device *dev,  char* throttle  )
{
        char* config = dev->cfgstring;
        char* throttle_amt = strchr(throttle, '-') + 1;
        char* throttle_cmd;
        char* device;
        char throttle_out[32];
        unsigned int throttle_val_iops=0;
        int string_mem;

        device = strrchr(config,'/') + 1;
        dbgp("Device  %s \n", device ) ;
        dbgp("Write throttle value  %s \n", throttle_amt );
        throttle_val_iops=atoi(throttle_amt);
        //itoa(throttle_val_bps, throttle_out, 10);
        sprintf(throttle_out,"%d",throttle_val_iops);//NB, it appears that itoa is not supported so vanilla sprintf instead to convert back to string - DC
        //below builds final string that is sent to BASH as a cgroup based throttling command - DC
        string_mem = asprintf(&throttle_cmd, "echo \"$(cat \"/sys/block/%s\"/dev) %s\" >> /sys/fs/cgroup/blkio/blkio.throttle.write_iops_device", device, throttle_out);

        if (string_mem == -1) {
                errp("ENOMEM\n");
                goto err;
        }

        system( throttle_cmd );

        free(throttle_cmd);

err:
        return;
}

int link_filter(struct tcmu_device *dev,  char* filter_verb)
{
        int ret;
        void* handle;
        void (*dl_print_msg)(char* msg);
        char* filter_path;
        char* filter_lib_name;
	char* stripped_filter_verb = NULL;//Ramon's mockup filter - DC 22/10/2016
	char* arg_token;
	char* arg_list = NULL;
        char* arg_end = NULL;
        
	if (strncmp ("rbt-",filter_verb,4) == 0) {
		dbgp("Received read throttle command  %s \n", filter_verb );
		apply_read_throttle_mbs( dev,  filter_verb );
                return 1;

	}

	if (strncmp ("wbt-",filter_verb,4) == 0) {
                dbgp("Received write throttle command  %s \n", filter_verb );
                apply_write_throttle_mbs( dev,  filter_verb );
                return 1;

        }

	if (strncmp ("rit-",filter_verb,4) == 0) {
                dbgp("Received read throttle IOPS command  %s \n", filter_verb );
                apply_read_throttle_iops( dev,  filter_verb );
                return 1;

        }

        if (strncmp ("wit-",filter_verb,4) == 0) {
                dbgp("Received write throttle IOPS command  %s \n", filter_verb );
                apply_write_throttle_iops( dev,  filter_verb );
                return 1;

        }
/*
	if (strncmp ("bop ",filter_verb,4) == 0) {
                dbgp("Received bop command  %s \n", filter_verb );
                return 1;

        }
*/  
    	debug_write (filter_verb);

	char* has_args = strchr(filter_verb, '(');//check for a list of arguments which will begin with '(' - DC 24/10/2016

	if(has_args==0){
		ret = asprintf(&filter_lib_name, "%s%s", filter_verb, ".so");
       		 if (ret == -1) {
               		 errp("ENOMEM\n");
       		 }
	}else{
		dbgp("Filter has args\n");
		ret = asprintf(&stripped_filter_verb, "%s", filter_verb);
                 if (ret == -1) {
                         errp("ENOMEM\n");
                 }

		arg_token = strchr(stripped_filter_verb, '(');
		if (arg_token != NULL) {
   			 *arg_token = '\0';
		}
		dbgp("Stripped filter verb =  %s\n", stripped_filter_verb );
		ret = asprintf(&filter_lib_name, "%s%s", stripped_filter_verb, ".so");
                 if (ret == -1) {
                         errp("ENOMEM\n");
                }
		dbgp("New filter lib name  =  %s \n", filter_lib_name );

		arg_list = arg_token + 1;
		arg_end = strchr(arg_list, ')');
		if (arg_end != NULL) {
                         *arg_end = '\0';
                }else{
			dbgp("Closing parenthesis missing from argument list  \n");
		}

		dbgp("Parsed argument list =  %s\n", arg_list );
//		free(stripped_filter_verb);

	}


        ret = asprintf(&filter_path, "%s/%s", default_filter_path, filter_lib_name);
        if (ret == -1) {
                errp("ENOMEM\n");
        }
        handle = dlopen(filter_path, RTLD_NOW|RTLD_LOCAL);
        if (!handle) {
        	debug_write (dlerror());
                errp("Could not open filter at : %s\n", dlerror());
                goto err;
        }
        dl_print_msg = dlsym(handle, "print_bind_msg");
        if (!dl_print_msg) {
                errp("dlsym failure \n");
                goto err;
        }


        dev->write_xform[dev->filter_cnt] = dlsym(handle, "write_xform");
        if (!dl_print_msg) {
               errp("dlsym failure \n");
               goto err;
        }

        dev->read_xform[dev->filter_cnt] = dlsym(handle, "read_xform");
        if (!dl_print_msg) {
               errp("dlsym failure \n");
               goto err;
        }
	//if (strcmp ("dedupcache",filter_verb) == 0)  // TODO: Just to be sage
	{ 
		dev->pre_read[dev->filter_cnt] = dlsym(handle, "pre_read");
	if (!dl_print_msg) {
		errp("dlsym failure \n");
		goto err;
	} }

	dev->get_filter_name[dev->filter_cnt] = dlsym(handle, "get_name");
        if (!dl_print_msg) {
               errp("dlsym failure \n");
               goto err;
	}

	dev->pass_args[dev->filter_cnt] = dlsym(handle, "pass_args");
        if (!dl_print_msg) {
               errp("dlsym failure \n");
               goto err;
        }

	if( arg_list != NULL){
		dbgp("Parameters being passed =  %s\n", arg_list);
		
		int args_passed = dev->pass_args[dev->filter_cnt]( arg_list );
		dbgp("Parameters accepted =   %d \n", args_passed);
	}
	
	//below is a special test harness for checking arguments passed to Ramon's mockup filter -DC 24/10/2016
	if (strncmp ("mockup(",filter_verb,7) == 0) {
                dbgp("Creating mockup filter and setting parameters  %s \n", filter_verb );
		int (*get_iters)();                
		int (*get_latency)();
		get_iters   = dlsym(handle, "get_iters");
		get_latency  = dlsym(handle, "get_latency");
		int tst_iters = get_iters();
		int tst_latency = get_latency();
		dbgp("Checking iters =  %d \n", tst_iters );
		dbgp("Checking latency =  %d \n", tst_latency );
		return 1;

        }

	//below is a special test harness for checking arguments passed to tstargs example filter -DC 24/10/2016
        if (strncmp ("tstargs(",filter_verb,8) == 0) {
                dbgp("Creating tstargs filter and setting parameters  %s \n", filter_verb );
                void*parg1  = dlsym(handle, "arg1");
                void*parg2  = dlsym(handle, "arg2");
                int *tst_arg1    = (int*)(parg1) ;
                float *tst_arg2  = (float*)(parg2) ;
                dbgp("Checking arg1 =  %d \n", *tst_arg1 );
                dbgp("Checking arg2 =  %f \n", *tst_arg2 );
                return 1;

        }

	dbgp("Completed run-time linkage of %s filter\n",dev->get_filter_name[dev->filter_cnt]() );

        free(filter_path);
        free(filter_lib_name);
	if( stripped_filter_verb ) free(stripped_filter_verb);
        dev->filter_cnt++;
        return 1;

err:
        free(filter_path);
        free(filter_lib_name);
	if( stripped_filter_verb ) free(stripped_filter_verb);
        return -1;

}
void parse_cfg_bind_filters(struct tcmu_device *dev)
{
        unsigned int i;
        unsigned int token_sep = 0;
        char* config = dev->cfgstring;
        char* has_filters = strchr(config, '>');//check for presence of filter seperator tokens, if non return
        if(has_filters==0) return;
        char* base = strchr(config, '/'); //first '/' after handler name
        char* top = strchr(base+2, '/');

        dbgp("Base =  %x: \n", base);
        dbgp("Top =  %x: \n", top);
        dbgp("Len =  %d: \n", top-base);

        for( i=0; i<top-base; i++)
        {
                if( base[i] =='>') token_sep++;
        }

        dbgp("Num tokens  =  %d: \n", token_sep);
        dbgp("Num filters =  %d: \n", token_sep-1);

        char* token;
        char* cp = strdupa(base+1);
        cp[top-base-1] = '\0';// terminate top of string
        const char delimiters[] = ">";
        token = strtok (cp, delimiters);
        dbgp("Linking %s filter... ", token);
        link_filter(dev, token);

        for(i=1;i<token_sep-1;i++)
        {
                token = strtok (NULL, delimiters);
                dbgp("Linking %s filter... ", token);
                link_filter(dev, token);

        }

}


static bool file_check_config(const char *cfgstring, char **reason)
{
	char *path;
	int fd;

	path = strchr(cfgstring, '/');
	if (!path) {
		asprintf(reason, "No path found");
		return false;
	}
//	path += 1; /* get past '/' */
	path += 1; /* get past '/' */
	path = strchr(cfgstring, '/');
	path += 1; /* get past '/' */
	path = strrchr(cfgstring, '/');
	dbgp("Check path = %s\n ", path);
	if (access(path, W_OK) != -1)
		return true; /* File exists and is writable */

	/* We also support creating the file, so see if we can create it */
	fd = creat(path, S_IRUSR | S_IWUSR);
	if (fd == -1) {
		asprintf(reason, "Could not create file");
		return false;
	}

	unlink(path);

	return true;
}

static int file_open(struct tcmu_device *dev)
{
	struct file_state *state;
	int64_t size;
	char *config;
	char* has_filters = 0;
	state = calloc(1, sizeof(*state));
	if (!state)
		return -1;

	dev->hm_private = state;

	dbgp("Raw configstring: %s\n", dev->cfgstring);
	has_filters = strchr(dev->cfgstring, '>');//check for filter seperator tokens in cfg string - DC
	if(has_filters)
		parse_cfg_bind_filters(dev);

	state->block_size = tcmu_get_attribute(dev, "hw_block_size");
	if (state->block_size == -1) {
		errp("Could not get device block size\n");
		goto err;
	}

	size = tcmu_get_device_size(dev);
	if (size == -1) {
		errp("Could not get device size\n");
		goto err;
	}

	state->num_lbas = size / state->block_size;

	config = strchr(dev->cfgstring, '/');
	if (!config) {
		errp("no configuration found in cfgstring\n");
		goto err;
	}
	config += 1; /* get past '/' */

	config = strchr(config, '/');//need to find second '/' for actual device - DC

	state->fd = open(config, O_CREAT | O_RDWR, S_IRUSR | S_IWUSR);
	if (state->fd == -1) {
		errp("could not open %s: %m\n", config);
		goto err;
	}

	return 0;

err:
	free(state);
	return -1;
}

static void file_close(struct tcmu_device *dev)
{
	struct file_state *state = dev->hm_private;

	close(state->fd);
	free(state);
}

static int set_medium_error(uint8_t *sense)
{
	return tcmu_set_sense_data(sense, MEDIUM_ERROR, ASC_READ_ERROR, NULL);
}

/*
 * Return scsi status or TCMU_NOT_HANDLED
 */
static int file_handle_cmd(
	struct tcmu_device *dev,
	uint8_t *cdb,
	struct iovec *iovec,
	size_t iov_cnt,
	uint8_t *sense)
{
	struct file_state *state = dev->hm_private;
	uint8_t cmd;
	int remaining;
	size_t ret;

	cmd = cdb[0];

	switch (cmd) {
	case INQUIRY:
		return tcmu_emulate_inquiry(dev, cdb, iovec, iov_cnt, sense);
		break;
	case TEST_UNIT_READY:
		return tcmu_emulate_test_unit_ready(cdb, iovec, iov_cnt, sense);
		break;
	case SERVICE_ACTION_IN_16:
		if (cdb[1] == READ_CAPACITY_16)
			return tcmu_emulate_read_capacity_16(state->num_lbas,
							     state->block_size,
							     cdb, iovec, iov_cnt, sense);
		else
			return TCMU_NOT_HANDLED;
		break;
	case MODE_SENSE:
	case MODE_SENSE_10:
		return tcmu_emulate_mode_sense(cdb, iovec, iov_cnt, sense);
		break;
	case MODE_SELECT:
	case MODE_SELECT_10:
		return tcmu_emulate_mode_select(cdb, iovec, iov_cnt, sense);
		break;
	case READ_6:
	case READ_10:
	case READ_12:
	case READ_16:
	{
		void *buf;
		uint64_t offset = state->block_size * tcmu_get_lba(cdb);
		int length = tcmu_get_xfer_length(cdb) * state->block_size;
		unsigned int i;		

		/* Using this buf DTRT even if seek is beyond EOF */
		buf = malloc(length);
		if (!buf)
			return set_medium_error(sense);
//		memset(buf, 0, length);
		bool doRead = true;
		if (dev->filter_cnt)
		{
			for(i = dev->filter_cnt; i ;i--){
			//	if (strcmp(dev->get_filter_name[i-1](), "DEDUPCACHE") == 0 )
				{
					dev->pre_read[i-1]( buf, length, offset, state->fd, &doRead);
				}
			}
		}	

		if (doRead)
		{
		
			ret = pread(state->fd, buf, length,offset);
			if (ret == -1) {
				errp("read failed: %m\n");
				free(buf);
				return set_medium_error(sense);
			}
		}

		if(dev->filter_cnt){//spawn out to process read filter stack - DC
                        for(i = dev->filter_cnt; i ;i--){
                                dev->read_xform[i-1]( (void*) buf, (unsigned long)length, (uint64_t)offset);
				dbgp("%s read filter executed \n", dev->get_filter_name[i-1]());//should only execute if debug is enabled - DC
				
			}
                }

		tcmu_memcpy_into_iovec(iovec, iov_cnt, buf, length);

		free(buf);

		return SAM_STAT_GOOD;
	}
	break;
	case WRITE_6:
	case WRITE_10:
	case WRITE_12:
	case WRITE_16:
	{
		uint64_t offset = state->block_size * tcmu_get_lba(cdb);
		int length = be16toh(*((uint16_t *)&cdb[7])) * state->block_size;
		unsigned int i;

		remaining = length;

		while (remaining) {
			unsigned int to_copy;
			bool doWrite = true;

			to_copy = (remaining > iovec->iov_len) ? iovec->iov_len : remaining;

			if(dev->filter_cnt){//spawn out and executed write transform stack - DC
                                for(i = 0; i < dev->filter_cnt; i++){
                                        dev->write_xform[i]( (void*) iovec->iov_base, (unsigned long)to_copy, (uint64_t)offset, &doWrite);
					dbgp("%s write filter executed \n", dev->get_filter_name[i]());//should only execute if debug is enabled - DC
                        	}
                        }
            if (doWrite)
            {
				ret = pwrite(state->fd, iovec->iov_base, to_copy, offset);
				if (ret == -1) {
					errp("Could not write: %m\n");
					return set_medium_error(sense);
				}
			} 
			offset += to_copy;
			remaining -= to_copy;
			iovec++;
		}

		return SAM_STAT_GOOD;
	}
	break;
	default:
		errp("unknown command %x\n", cdb[0]);
		return TCMU_NOT_HANDLED;
	}
}

static const char file_cfg_desc[] =
	"The path to the file to use as a backstore.";

static struct tcmu_handler filter_stack_handler = {
	.name = "MPStor top level filter stack",
	.subtype = "mp_filter_stack",
	.cfg_desc = file_cfg_desc,

	.check_config = file_check_config,

	.open = file_open,
	.close = file_close,
	.handle_cmd = file_handle_cmd,
};

/* Entry point must be named "handler_init". */
void handler_init(void)
{
	tcmu_register_handler(&filter_stack_handler);
}
