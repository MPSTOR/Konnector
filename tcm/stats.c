#include <stdio.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

// Should be equal to ocompress filter
#define DEBUG 0

#define NUM_PREFETCH 150000
// 10000 Cached reads
#define GZIP_ENCODING   16
#define CHUNK       40960
#define BLOCKSIZE 4096


#define MAGICCONST 0x01663
#define DISKRECORDS 5000000 // 20 GB of UNCOMPRESSED SPACE
#define DIRTYBLOCKS 10000   // 10000 compressed blocks that we can have dirty, and if we hit 10000 we put a reordering process.  // TODO Place to optimize
#define SIZERECORD 10 // 10 bytes, one unsigned long long plus a unsigned short
#define HEADER 24 // 8 MAGIC 8 LBLOCK 8 DIRTY
#define MINCOMP 100  // minimum compressed block optimization



int main (int argc, char ** argv)
{
	char diskdevice[100];
	
	
	if (argc > 1 ) { strcpy(diskdevice, argv[1]); printf ("Stats for disk : %s\n", diskdevice); }
	 
	// Test 1 : Write at different zones a complete aligned block
	int fd = open (diskdevice,O_RDONLY);
	

	unsigned long long DRECORD;
	double CSIZE = 0.0;
	double RSIZE = 0.0;

	for (int i = 0 ; i < DISKRECORDS; i++)
	{
		unsigned long long compressedBlock;
		unsigned short compressedSize;

	    lseek (fd, ( i ) * SIZERECORD + HEADER , SEEK_SET);
	    read (fd, &compressedBlock, sizeof(unsigned long long));
	    read (fd, &compressedSize, sizeof(unsigned short));
	 
	    if (compressedSize != 0 ) 
	    {
	    	CSIZE += compressedSize;
	    	RSIZE += BLOCKSIZE;
	    }
	}
	

	printf ("Output compress filter Stats : \n");
	printf ("Compressed Data : %lf MB Real Data : %lf MB Ratio : %lf\n", CSIZE/(1024.0*1024.0), RSIZE/(1024.0*1024.0), (1.0 - CSIZE / RSIZE) * 100.0);
}
